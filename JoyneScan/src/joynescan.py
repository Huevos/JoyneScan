# for localized messages
from . import _

from Components.ActionMap import ActionMap
from Components.config import config, getConfigListEntry, configfile
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.NimManager import nimmanager
from Components.ProgressBar import ProgressBar
from Components.Sources.StaticText import StaticText
from Components.Sources.FrontendStatus import FrontendStatus
from Components.Sources.Progress import Progress

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from about import JoyneScan_About
from downloadbar import downloadBar
from lamedbreader import LamedbReader
from lamedbwriter import LamedbWriter
from providers import PROVIDERS

from enigma import eTimer, eDVBFrontendParametersSatellite, eDVBFrontendParameters, eDVBResourceManager

from time import localtime, time, strftime, mktime, sleep
import datetime

from Plugins.SystemPlugins.AutoBouquetsMaker.scanner import dvbreader


class JoyneScan(Screen): # the downloader
	skin = downloadBar()
	
	def __init__(self, session, args = None):
		self.config = config.plugins.joynescan
		self.debugName = "JoyneScan"
		self.extra_debug = self.config.extra_debug.value
		self.screentitle = _("Joyne Scan")
		print "[%s][__init__] Starting..." % (self.debugName,)
		print "[%s][__init__] args" % (self.debugName,), args
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, self.screentitle)

		self["action"] = Label(_("Starting scanner"))
		self["status"] = Label("")
		self["progress"] = ProgressBar()
		self["progress_text"] = Progress()
		self["tuner_text"] = Label("")

		# don't forget to disable this ActionMap before writing to any settings files
		self["actions"] = ActionMap(["SetupActions"],
		{
			"cancel": self.keyCancel,
		}, -2)

		self.selectedNIM = -1
		if args:
			pass
		self.frontend = None
		self["Frontend"] = FrontendStatus(frontend_source = lambda : self.frontend, update_interval = 100)
		self.rawchannel = None
		self.postScanService = None # self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.LOCK_TIMEOUT_ROTOR = 1200 	# 100ms for tick - 120 sec
		self.LOCK_TIMEOUT_FIXED = 50 	# 100ms for tick - 5 sec

		self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_FIXED

		self.TIMEOUT_NIT = 30
		self.TIMEOUT_BAT = 30
		self.TIMEOUT_SDT = 5
		
		self.path = "/etc/enigma2" # path to settings files



		self.homeTransponder = PROVIDERS[self.config.provider.value]["transponder"]
		self.bat = PROVIDERS[self.config.provider.value]["bat"]

		self.descriptors = {"transponder": 0x43, "serviceList": 0x41, "bouquet": self.bat["descriptor"]}

		self.transponders_dict = {} # overwritten in firstExec
		
		self.services_dict = {}
		self.tmp_services_dict = {}
		self.namespace_dict = {} # to store namespace when sub network is enabled
		self.logical_channel_number_dict = {}
		self.ignore_visible_service_flag = False # make this a user override later if found necessary. Visible service flag is currently available in the NIT and BAT on Joyne home transponders
		self.VIDEO_ALLOWED_TYPES = [1, 4, 5, 17, 22, 24, 25, 27, 135]
		self.AUDIO_ALLOWED_TYPES = [2, 10]
		self.BOUQUET_PREFIX = "userbouquet.JoyneScan."
		self.bouquetsIndexFilename = "bouquets.tv"
		self.bouquetFilename = self.BOUQUET_PREFIX + self.config.provider.value + ".tv"
		self.bouquetName = PROVIDERS[self.config.provider.value]["name"] # already translated
		self.currentAction = 0
		self.actions = ["read NIT", "read BAT",] # "readSDTs"]

		self.adapter = 0 # fix me
		
		self.nit_pid = 0x10 # DVB default
		self.nit_current_table_id = 0x40 # DVB default
		self.nit_other_table_id = 0x41 # DVB default
		self.sdt_pid = 0x11 # DVB default
		self.sdt_current_table_id = 0x42 # DVB default
		self.sdt_other_table_id = 0x46 # DVB default
		self.bat_pid = 0x11 # DVB default
		self.bat_table_id = 0x4a # DVB default

		self.SDTscanList = []

		self.polarization_dict = {
			eDVBFrontendParametersSatellite.Polarisation_Horizontal: "H", 
			eDVBFrontendParametersSatellite.Polarisation_Vertical: "V", 
			eDVBFrontendParametersSatellite.Polarisation_CircularLeft: "L", 
			eDVBFrontendParametersSatellite.Polarisation_CircularRight: "R"
		}
		
		self.namespace_complete = not (config.usage.subnetwork.value if hasattr(config.usage, "subnetwork") else True) # config.usage.subnetwork not available in all distros/images
		self.onFirstExecBegin.append(self.firstExec)

	def firstExec(self):
		from Screens.Standby import inStandby

		self.progresscount = 8
		self.progresscurrent = 1
		
		if not inStandby:
			self["action"].setText(_("Reading current settings..."))
			self["progress_text"].range = self.progresscount
			self["progress_text"].value = self.progresscurrent
			self["progress"].setRange((0, self.progresscount))
			self["progress"].setValue(self.progresscurrent)
		self.transponders_dict = LamedbReader().readLamedb(self.path)
		self.progresscurrent += 1
		if not inStandby:
			self["action"].setText(_("Current settings read..."))
			self["progress_text"].value = self.progresscurrent
			self["progress"].setValue(self.progresscurrent)

		self.timer = eTimer()
		self.timer.callback.append(self.readStreams)
		self.timer.start(100, 1)

	def readStreams(self):
		if len(self.actions) > self.currentAction and self.actions[self.currentAction] == "read NIT":
			self.transpondercurrent = self.homeTransponder
			
			self.timer = eTimer()
			self.timer.callback.append(self.getFrontend)
			self.timer.start(100, 1)

	def getFrontend(self):
		from Screens.Standby import inStandby
		if not inStandby:
			self["action"].setText(_("Tuning %s on %s %s...") % (self.bouquetName, str(self.transpondercurrent["frequency"]/1000), self.polarization_dict.get(self.transpondercurrent["polarization"],"")))
		print "[%s][getFrontend] searching for available tuner" % (self.debugName,)
		nimList = []
		for nim in nimmanager.nim_slots:
			if not nim.isCompatible("DVB-S") or \
				nim.isFBCLink() or \
				(hasattr(nim, 'config_mode_dvbs') and nim.config_mode_dvbs or nim.config_mode) in ("loopthrough", "satposdepends", "nothing") or \
				self.transpondercurrent["orbital_position"] not in [sat[0] for sat in nimmanager.getSatListForNim(nim.slot)]:
				continue
			nimList.append(nim.slot)

		if len(nimList) == 0: # No nims found for this satellite
			print "[%s][getFrontend] No compatible tuner found" % (self.debugName,)
			if len(self.actions) > self.currentAction and self.actions[self.currentAction] in ("read NIT", "read BAT"):
				self.showError(_("No compatible tuner found"))
			else:
				self.currentAction += 1
				self.readStreams()
			return

		resmanager = eDVBResourceManager.getInstance()
		if not resmanager:
			print "[%s][getFrontend] Cannot retrieve Resource Manager instance" % (self.debugName,)
			self.showError(_('Cannot retrieve Resource Manager instance'))
			return

		# stop pip if running
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
			print "[%s][getFrontend] Stopping PIP." % (self.debugName,)

		# stop currently playing service if it is using a tuner in ("loopthrough", "satposdepends")
		currentlyPlayingNIM = None
		currentService = self.session and self.session.nav.getCurrentService()
		frontendInfo = currentService and currentService.frontendInfo()
		frontendData = frontendInfo and frontendInfo.getAll(True)
		if frontendData is not None:
			currentlyPlayingNIM = frontendData.get("tuner_number", None)
			if currentlyPlayingNIM is not None and nimmanager.nim_slots[currentlyPlayingNIM].isCompatible("DVB-S"):
				nimConfigMode = hasattr(nimmanager.nim_slots[currentlyPlayingNIM], "config_mode_dvbs") and nimmanager.nim_slots[currentlyPlayingNIM].config_mode_dvbs or nimmanager.nim_slots[currentlyPlayingNIM].config_mode
				if nimConfigMode in ("loopthrough", "satposdepends"):
					self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
					self.session.nav.stopService()
					currentlyPlayingNIM = None
					print "[%s][getFrontend] The active service was using a %s tuner, so had to be stopped (slot id %s)." % (self.debugName, nimConfigMode, currentlyPlayingNIM)
		del frontendInfo
		del currentService

		current_slotid = -1
		if self.rawchannel:
			del(self.rawchannel)

		self.frontend = None
		self.rawchannel = None

		nimList = [slot for slot in nimList if not self.isRotorSat(slot, self.transpondercurrent["orbital_position"])] + [slot for slot in nimList if self.isRotorSat(slot, self.transpondercurrent["orbital_position"])] #If we have a choice of dishes, try "fixed" before "motorised".
		for slotid in nimList:
			if current_slotid == -1:	# mark the first valid slotid in case of no other one is free
				current_slotid = slotid

			self.rawchannel = resmanager.allocateRawChannel(slotid)
			if self.rawchannel:
				print "[%s][getFrontend] Nim found on slot id %d with sat %s" % (self.debugName, slotid, nimmanager.getSatName(self.transpondercurrent["orbital_position"]))
				current_slotid = slotid
				break

			if self.rawchannel:
				break

		if current_slotid == -1:
			print "[%s][getFrontend] No valid NIM found for %s" % (self.debugName, self.bouquetName)
			self.showError(_('No valid NIM found for %s') % self.bouquetName)
			return

		if not self.rawchannel:
			# if we are here the only possible option is to close the active service
			if currentlyPlayingNIM in nimList:
				slotid = currentlyPlayingNIM
				print "[%s][getFrontend] Nim found on slot id %d but it's busy. Stopping active service" % (self.debugName, slotid)
				self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
				self.session.nav.stopService()
				self.rawchannel = resmanager.allocateRawChannel(slotid)
				if self.rawchannel:
					print "[%s][getFrontend] The active service was stopped, and the NIM is now free to use." % (self.debugName,)
					current_slotid = slotid

			if not self.rawchannel:
				if self.session.nav.RecordTimer.isRecording():
					print "[%s][getFrontend] Cannot free NIM because a recording is in progress" % (self.debugName,)
					self.showError(_('Cannot free NIM because a recording is in progress'))
					return
				else:
					print "[%s][getFrontend] Cannot get the NIM" % (self.debugName,)
					self.showError(_('Cannot get the NIM'))
					return

		# set extended timeout for rotors
		self.motorised = False
		if self.isRotorSat(current_slotid, self.transpondercurrent["orbital_position"]):
			self.motorised = True
			self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_ROTOR
			print "[%s][getFrontend] Motorised dish. Will wait up to %i seconds for tuner lock." % (self.debugName, self.LOCK_TIMEOUT/10)
		else:
			self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_FIXED
			print "[%s][getFrontend] Fixed dish. Will wait up to %i seconds for tuner lock." % (self.debugName, self.LOCK_TIMEOUT/10)

		self.selectedNIM = current_slotid  # Remember for downloading SI tables
		
		self["tuner_text"].setText(chr(ord('A') + current_slotid))

		self.current_slotid = current_slotid
		
		self.frontend = self.rawchannel.getFrontend()
		if not self.frontend:
			print "[%s][getFrontend] Cannot get frontend" % (self.debugName,)
			self.showError(_('Cannot get frontend'))
			return

		self.demuxer_id = self.rawchannel.reserveDemux()
		if self.demuxer_id < 0:
			print "[%s][doTune] Cannot allocate the demuxer." % (self.debugName,)
			self.showError(_('Cannot allocate the demuxer.'))
			return

		params_fe = eDVBFrontendParameters()
		params_fe.setDVBS(self.setParams(), False)

		self.frontend.tune(params_fe)

		self.lockcounter = 0
		self.locktimer = eTimer()
		self.locktimer.callback.append(self.checkTunerLock)
		self.locktimer.start(100, 1)

	def checkTunerLock(self):
		from Screens.Standby import inStandby
		self.dict = {}
		self.frontend.getFrontendStatus(self.dict)
		if self.dict["tuner_state"] == "TUNING":
			if self.lockcounter < 1: # only show this once in the log per retune event
				print "[%s][checkTunerLock] TUNING" % self.debugName
		elif self.dict["tuner_state"] == "LOCKED":
			if not inStandby:
				self["action"].setText(_("Reading %s on %s %s...") % (self.bouquetName, str(self.transpondercurrent["frequency"]/1000), self.polarization_dict.get(self.transpondercurrent["polarization"],"")))
				#self["status"].setText(_("???"))

			self.readTransponderCounter = 0
			self.readTranspondertimer = eTimer()
			self.readTranspondertimer.callback.append(self.readTransponder)
			self.readTranspondertimer.start(100, 1)
			return
		elif self.dict["tuner_state"] in ("LOSTLOCK", "FAILED"):
			print "[%s][checkTunerLock] TUNING FAILED" % self.debugName
			if len(self.actions) > self.currentAction and self.actions[self.currentAction] in ("read NIT", "read BAT"):
				self.showError(_("Tuning failed on %d") % self.transpondercurrent["frequency"]/1000)
			else:
				self.currentAction += 1
				self.readStreams()
			return

		self.lockcounter += 1
		if self.lockcounter > self.LOCK_TIMEOUT:
			print "[%s][checkTunerLock] Timeout for tuner lock" % self.debugName
			if len(self.actions) > self.currentAction and self.actions[self.currentAction] in ("read NIT", "read BAT"):
				self.showError(_("Timeout for tuner lock on %d") % self.transpondercurrent["frequency"]/1000)
			else:
				self.currentAction += 1
				self.readStreams()
			return
		self.locktimer.start(100, 1)

	def readTransponder(self):
		if self.motorised and not self.tsidOnidTest(self.transpondercurrent["original_network_id"], self.transpondercurrent["transport_stream_id"]):
			print "[%s][readTransponder] Could not acquire the correct tsid/onid on the home transponder." % self.debugName
			if len(self.actions) > self.currentAction and self.actions[self.currentAction] in ("read NIT", "read BAT"):
				self.showError(_("Could not acquire the correct tsid/onid on the home transponder."))
			else:
				self.currentAction += 1
				self.readStreams()
			return

		if len(self.actions) > self.currentAction and self.actions[self.currentAction] in ("read NIT",):
			if self.readNIT():
				pass

	def tsidOnidTest(self, onid=None, tsid=None):
		# This just grabs the tsid and onid of the current transponder.
		# Used to confirm motorised dishes have arrived at the correct satellite before starting the download.
		print "[%s] tsid onid test..." % self.debugName

		sdt_pid = 0x11
		sdt_current_table_id = 0x42
		mask = 0xff
		tsidOnidTestTimeout = 90
		passed_test = False
		
		self.setDemuxer()

		fd = dvbreader.open(self.demuxer_device, sdt_pid, sdt_current_table_id, mask, self.current_slotid)
		if fd < 0:
			print "[%s][tsidOnidTest] Cannot open the demuxer_device '%s'" % (self.debugName, demuxer_device)
			return None

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, tsidOnidTestTimeout)

		while True:
			if datetime.datetime.now() > timeout:
				print "[%s][tsidOnidTest] Timed out checking tsid onid" % self.debugName
				break

			section = dvbreader.read_sdt(fd, sdt_current_table_id, 0x00)
			if section is None:
				sleep(0.1)	# no data.. so we wait a bit
				continue

			if section["header"]["table_id"] == sdt_current_table_id:
				passed_test = (onid is None or onid == section["header"]["original_network_id"]) and (tsid is None or tsid == section["header"]["transport_stream_id"])
				print "[%s][tsidOnidTest] tsid: %d, onid: %d" % (self.debugName, section["header"]["transport_stream_id"], section["header"]["original_network_id"])
				if passed_test:
					break

		dvbreader.close(fd)

		return passed_test

	def readNIT(self, read_other_section=True):
		print "[%s] Reading NIT..." % self.debugName

		if self.nit_other_table_id == 0x00:
			mask = 0xff
		else:
			mask = self.nit_current_table_id ^ self.nit_other_table_id ^ 0xff

		self.setDemuxer()

		fd = dvbreader.open(self.demuxer_device, self.nit_pid, self.nit_current_table_id, mask, self.current_slotid)
		if fd < 0:
			print "[%s] Cannot open the demuxer" % self.debugName
			print "[%s] demuxer_device" % self.debugName, str(self.demuxer_device)
			print "[%s] nit_pid" % self.debugName, str(self.nit_pid)
			print "[%s] nit_current_table_id" % self.debugName, str(self.nit_current_table_id)
			print "[%s] mask", str(mask)
			print "[%s] current_slotid" % self.debugName, str(self.current_slotid)
			return None

		nit_current_section_version = -1
		nit_current_section_network_id = -1
		nit_current_sections_read = []
		nit_current_sections_count = 0
		nit_current_content = []
		nit_current_completed = False

		nit_other_section_version = {}
		nit_other_sections_read = {}
		nit_other_sections_count = {}
		nit_other_content = {}
		nit_other_completed = {}
		all_nit_others_completed = not read_other_section or self.nit_other_table_id == 0x00

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.TIMEOUT_NIT)
		while True:
			if datetime.datetime.now() > timeout:
				print "[%s] Timed out reading NIT" % self.debugName
				if self.nit_other_table_id != 0x00:
					print "[%s] No nit_other found - set nit_other_table_id=\"0x00\" for faster scanning?" % self.debugName
				break

			section = dvbreader.read_nit(fd, self.nit_current_table_id, self.nit_other_table_id)
			if section is None:
				sleep(0.1)	# no data.. so we wait a bit
				continue

			if self.extra_debug:
				print "[%s] NIT raw section header" % self.debugName, section["header"]
				print "[%s] NIT raw section content" % self.debugName, section["content"]

			if (section["header"]["table_id"] == self.nit_current_table_id and not nit_current_completed):
				if self.extra_debug:
					print "[%s] raw section above is from NIT actual table." % self.debugName

				if (section["header"]["version_number"] != nit_current_section_version or section["header"]["network_id"] != nit_current_section_network_id):
					nit_current_section_version = section["header"]["version_number"]
					nit_current_section_network_id = section["header"]["network_id"]
					nit_current_sections_read = []
					nit_current_content = []
					nit_current_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in nit_current_sections_read:
					nit_current_sections_read.append(section["header"]["section_number"])
					nit_current_content += section["content"]

					if len(nit_current_sections_read) == nit_current_sections_count:
						nit_current_completed = True

			elif section["header"]["table_id"] == self.nit_other_table_id and not all_nit_others_completed:
				if self.extra_debug:
					print "[%s] raw section above is from NIT other table." % self.debugName
				network_id = section["header"]["network_id"]

				if network_id in nit_other_section_version and nit_other_section_version[network_id] == section["header"]["version_number"] and all(completed == True for completed in nit_other_completed.itervalues()):
					all_nit_others_completed = True
				else:

					if network_id not in nit_other_section_version or section["header"]["version_number"] != nit_other_section_version[network_id]:
						nit_other_section_version[network_id] = section["header"]["version_number"]
						nit_other_sections_read[network_id] = []
						nit_other_content[network_id] = []
						nit_other_sections_count[network_id] = section["header"]["last_section_number"] + 1
						nit_other_completed[network_id] = False

					if section["header"]["section_number"] not in nit_other_sections_read[network_id]:
						nit_other_sections_read[network_id].append(section["header"]["section_number"])
						nit_other_content[network_id] += section["content"]

						if len(nit_other_sections_read[network_id]) == nit_other_sections_count[network_id]:
							nit_other_completed[network_id] = True

			elif self.extra_debug:
				print "[%s] raw section above skipped. Either duplicate output or ID mismatch."

			if nit_current_completed and all_nit_others_completed:
				break

		dvbreader.close(fd)

		nit_content = nit_current_content
		for network_id in nit_other_content:
			nit_content += nit_other_content[network_id]

		if self.extra_debug:
			for x in nit_content:
				print "[%s] NIT item:" % self.debugName, x

		#transponders_tmp = [x for x in nit_content if "descriptor_tag" in x and x["descriptor_tag"] == self.descriptors["transponder"]]
		transponders_count = self.processTransponders([x for x in nit_content if "descriptor_tag" in x and x["descriptor_tag"] == self.descriptors["transponder"]])
		self["status"].setText(_("nsponders found: %d") % transponders_count)
		services_tmp = [x for x in nit_content if "descriptor_tag" in x and x["descriptor_tag"] == self.descriptors["serviceList"]]

	def processTransponders(self, transponderList):
		transponders_count = 0
		for transponder in transponderList:
			transponder["orbital_position"] = self.getOrbPosFromBCD(transponder)
			if not nimmanager.getNimListForSat(transponder["orbital_position"]): # Don't waste effort trying to scan or import from not configured satellites.
				if self.extra_debug:
					print "[%s] Skipping transponder as it is on a not configured satellite:" % self.debugName, transponder
				continue
			transponder["flags"] = 0
			transponder["frequency"] = int(round(transponder["frequency"]*10, -3)) # Number will be five digits according to SI output, plus 3 trailing zeros. This is the same format used in satellites.xml.
			transponder["symbol_rate"] = int(round(transponder["symbol_rate"]*100, -3))
			if transponder["fec_inner"] != eDVBFrontendParametersSatellite.FEC_None and transponder["fec_inner"] > eDVBFrontendParametersSatellite.FEC_9_10:
				transponder["fec_inner"] = eDVBFrontendParametersSatellite.FEC_Auto
			if transponder["system"] == eDVBFrontendParametersSatellite.System_DVB_S and transponder["modulation"] == eDVBFrontendParametersSatellite.Modulation_8PSK:
				transponder["modulation"] = eDVBFrontendParametersSatellite.Modulation_QPSK
			transponder["inversion"] = eDVBFrontendParametersSatellite.Inversion_Unknown
			transponder["namespace"] = self.buildNamespace(transponder)

			key = "%x:%x:%x" % (transponder["namespace"],
				transponder["transport_stream_id"],
				transponder["original_network_id"])

			if key in self.transponders_dict:
				transponder["services"] = self.transponders_dict[key]["services"]
			self.transponders_dict[key] = transponder
			transponders_count += 1

			namespace_key = "%x:%x" % (transponder["transport_stream_id"], transponder["original_network_id"])
			if namespace_key not in self.namespace_dict:
				self.namespace_dict[namespace_key] = transponder["namespace"]

			if self.extra_debug:
				print "[%s] transponder" % self.debugName, transponder

			self.SDTscanList.append(transponder)
			self.actions.append("read SDTs") # Add new task to actions list to scan SDT of this transponder.

		return transponders_count

	def buildNamespace(self, transponder):
		namespace = transponder['orbital_position'] << 16
		if self.namespace_complete or not self.isValidOnidTsid(transponder):
			namespace |= ((transponder['frequency'] / 1000) & 0xFFFF) | ((transponder['polarization'] & 1) << 15)
		return namespace

	def isValidOnidTsid(self, transponder):
		return transponder["original_network_id"] != 0x0 and transponder["original_network_id"] < 0xff00

	def getOrbPosFromBCD(self, transponder):
		# convert 4 bit BCD (binary coded decimal)
		# west_east_flag, 0 == west, 1 == east
		op = 0
		bits = 4
		bcd = transponder["orbital_position"]
		for i in range(bits):
			op += ((bcd >> 4*i) & 0x0F) * 10**i
		return op and not transponder["west_east_flag"] and 3600 - op or op

	def setDemuxer(self):
		self.demuxer_device = "/dev/dvb/adapter%d/demux%d" % (self.adapter, self.demuxer_id)
		print "[%s] Demuxer %d" % (self.debugName, self.demuxer_id)

	def setParams(self):
		params = eDVBFrontendParametersSatellite()
		params.frequency = self.transpondercurrent["frequency"]
		params.symbol_rate = self.transpondercurrent["symbol_rate"]
		params.polarisation = self.transpondercurrent["polarization"]
		params.fec = self.transpondercurrent["fec_inner"]
		params.inversion = eDVBFrontendParametersSatellite.Inversion_Unknown
		params.orbital_position = self.transpondercurrent["orbital_position"]
		params.system = self.transpondercurrent["system"]
		params.modulation = self.transpondercurrent["modulation"]
		params.rolloff = self.transpondercurrent["roll_off"]
		params.pilot = eDVBFrontendParametersSatellite.Pilot_Unknown
		if hasattr(eDVBFrontendParametersSatellite, "No_Stream_Id_Filter"):
			params.is_id = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
		if hasattr(eDVBFrontendParametersSatellite, "PLS_Gold"):
			params.pls_mode = eDVBFrontendParametersSatellite.PLS_Gold
		if hasattr(eDVBFrontendParametersSatellite, "PLS_Default_Gold_Code"):
			params.pls_code = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
		if hasattr(eDVBFrontendParametersSatellite, "No_T2MI_PLP_Id"):
			params.t2mi_plp_id = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
		if hasattr(eDVBFrontendParametersSatellite, "T2MI_Default_Pid"):
			params.t2mi_pid = eDVBFrontendParametersSatellite.T2MI_Default_Pid
		return params

	def showError(self, message):
		from Screens.Standby import inStandby
		self.releaseFrontend()
		self.restartService()
		if not inStandby:
			question = self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)
			question.setTitle(self.screentitle)
		self.close()

	def keyCancel(self):
		self.releaseFrontend()
		self.restartService()
		self.close()

	def releaseFrontend(self):
		if hasattr(self, 'frontend'):
			del self.frontend
		if hasattr(self, 'rawchannel'):
			del self.rawchannel
		self.frontend = None
		self.rawchannel = None

	def restartService(self):
		if self.postScanService:
			self.session.nav.playService(self.postScanService)
			self.postScanService = None
	
	def isRotorSat(self, slot, orb_pos):
		rotorSatsForNim = nimmanager.getRotorSatListForNim(slot)
		if len(rotorSatsForNim) > 0:
			for sat in rotorSatsForNim:
				if sat[0] == orb_pos:
					return True
		return False



class JoyneScan_Setup(ConfigListScreen, Screen):
	def __init__(self, session, args = None):
		Screen.__init__(self, session)
		self.setup_title = _('JoyneScan') + " - " + _('Setup')
		Screen.setTitle(self, self.setup_title)
		self.skinName = ["JoyneScan_Setup", "Setup"]
		self.config = config.plugins.joynescan
		self.onChangedEntry = []
		self.session = session
		ConfigListScreen.__init__(self, [], session = session, on_change = self.changedEntry)

		self["actions2"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"ok": self.keyOk,
			"menu": self.keyCancel,
			"cancel": self.keyCancel,
			"save": self.keySave,
			"red": self.keyCancel,
			"green": self.keySave,
			"yellow": self.keyGo,
			"blue": self.keyAbout
		}, -2)

		self["key_red"] = StaticText(_("Exit"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText(_("Download"))
		self["key_blue"] = StaticText(_("About"))

		self["description"] = Label("")

		self.createSetup()

		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def createSetup(self):
		indent = "- "
		self.list = []

		self.list.append(getConfigListEntry(_("Provider"), self.config.provider, _('Select the provider you wish to scan.')))
		self.list.append(getConfigListEntry(_("Show in extensions menu"), self.config.extensions, _('When enabled, this allows you start a Joyne update from the extensions list.')))

		self.list.append(getConfigListEntry(_("Scheduled fetch"), self.config.schedule, _("Set up a task scheduler to periodically update Joyne data.")))
		if self.config.schedule.value:
			self.list.append(getConfigListEntry(indent + _("Schedule time of day"), self.config.scheduletime, _("Set the time of day to run JoyneScan.")))
			self.list.append(getConfigListEntry(indent + _("Schedule days of the week"), self.config.dayscreen, _("Press OK to select which days to run JoyneScan.")))
			self.list.append(getConfigListEntry(indent + _("Schedule wake from deep standby"), self.config.schedulewakefromdeep, _("If the receiver is in 'Deep Standby' when the schedule is due wake it up to run JoyneScan.")))
			if self.config.schedulewakefromdeep.value:
				self.list.append(getConfigListEntry(indent + _("Schedule return to deep standby"), self.config.scheduleshutdown, _("If the receiver was woken from 'Deep Standby' and is currently in 'Standby' and no recordings are in progress return it to 'Deep Standby' once the import has completed.")))
		self.list.append(getConfigListEntry(_("Extra debug"), self.config.extra_debug, _("This feature is for development only. Requires debug logs to be enabled or enigma2 to be started in console mode (at debug level 4.")))

		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def keyOk(self):
		if self["config"].getCurrent() and len(self["config"].getCurrent()) > 1 and self["config"].getCurrent()[1] == self.config.dayscreen:
			self.session.open(JoyneScanDaysScreen)
		else:
			self.keySave()

	def keyCancel(self):
		if self["config"].isChanged():
			self.session.openWithCallback(self.cancelCallback, MessageBox, _("Really close without saving settings?"))
		else:
			self.cancelCallback(True)

	def cancelCallback(self, answer):
		if answer:
			for x in self["config"].list:
				x[1].cancel()
			self.close(False)

	def keySave(self):
		self.saveAll()
		self["description"].setText(_("The current configuration has been saved.") + (self.scheduleInfo and " " + _("Next scheduled fetch is programmed for %s.") % self.scheduleInfo + " " or " "))

	def keyGo(self):
		self.saveAll()
		self.startDownload()

	def startDownload(self):
		print "[JoyneScan] startDownload"
		self.session.openWithCallback(self.joynescanCallback, JoyneScan, {})

	def joynescanCallback(self):
		pass

	def keyAbout(self):
		self.session.open(JoyneScan_About)

	def selectionChanged(self):
		self["description"].setText(self.getCurrentDescription()) #self["description"].setText(self["config"].getCurrent()[2])

	# for summary:
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()
		if self["config"].getCurrent() and len(self["config"].getCurrent()) > 1 and self["config"].getCurrent()[1] in (self.config.schedule, self.config.schedulewakefromdeep):
			self.createSetup()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def createSummary(self):
		from Screens.Setup import SetupSummary
		return SetupSummary
	# end: for summary

	def saveAll(self):
		for x in self["config"].list:
			x[1].save()

		configfile.save()
		try:
			self.scheduleInfo = AutoScheduleTimer.instance.doneConfiguring()
		except AttributeError as e:
			print "[JoyneScan] Timer.instance not available for reconfigure.", e
			self.scheduleInfo = ""


class  JoyneScanDaysScreen(ConfigListScreen, Screen):
	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _('JoyneScan') + " - " + _("Select days"))
		self.skinName = ["Setup"]
		self.config = config.plugins.joynescan
		self.list = []
		days = (_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"), _("Friday"), _("Saturday"), _("Sunday"))
		for i in sorted(self.config.days.keys()):
			self.list.append(getConfigListEntry(days[i], self.config.days[i]))
		ConfigListScreen.__init__(self, self.list)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.keyCancel,
			"green": self.keySave,
			"save": self.keySave,
			"cancel": self.keyCancel,
			"ok": self.keySave,
		}, -2)

	def keySave(self):
		if not any([self.config.days[i].value for i in self.config.days]):
			info = self.session.open(MessageBox, _("At least one day of the week must be selected"), MessageBox.TYPE_ERROR, timeout = 30)
			info.setTitle(_('JoyneScan') + " - " + _("Select days"))
			return
		for x in self["config"].list:
			x[1].save()
		self.close()

	def keyCancel(self):
		if self["config"].isChanged():
			self.session.openWithCallback(self.cancelCallback, MessageBox, _("Really close without saving settings?"))
		else:
			self.cancelCallback(True)

	def cancelCallback(self, answer):
		if answer:
			for x in self["config"].list:
				x[1].cancel()
			self.close(False)


autoScheduleTimer = None
def Scheduleautostart(reason, session=None, **kwargs):
	#
	# This gets called twice at start up, once by WHERE_AUTOSTART without session,
	# and once by WHERE_SESSIONSTART with session. WHERE_AUTOSTART is needed though
	# as it is used to wake from deep standby. We need to read from session so if
	# session is not set just return and wait for the second call to this function.
	#
	# Called with reason=1 during /sbin/shutdown.sysvinit, and with reason=0 at startup.
	# Called with reason=1 only happens when using WHERE_AUTOSTART.
	# If only using WHERE_SESSIONSTART there is no call to this function on shutdown.
	#
	print "[JoyneScan-Scheduler][Scheduleautostart] reason(%d), session" % reason, session
	if reason == 0 and session is None:
		return
	global autoScheduleTimer
	global wasScheduleTimerWakeup
	wasScheduleTimerWakeup = False
	now = int(time())
	if reason == 0:
		if config.plugins.joynescan.schedule.value:
			# check if box was woken up by a timer, if so, check if this plugin set this timer. This is not conclusive.
			if session.nav.wasTimerWakeup() and abs(config.plugins.joynescan.nextscheduletime.value - time()) <= 450:
				wasScheduleTimerWakeup = True
				# if box is not in standby do it now
				from Screens.Standby import Standby, inStandby
				if not inStandby:
					# hack alert: session requires "pipshown" to avoid a crash in standby.py
					if not hasattr(session, "pipshown"):
						session.pipshown = False
					from Tools import Notifications
					Notifications.AddNotificationWithID("Standby", Standby)

		print"[JoyneScan-Scheduler][Scheduleautostart] AutoStart Enabled"
		if autoScheduleTimer is None:
			autoScheduleTimer = AutoScheduleTimer(session)
	else:
		print"[JoyneScan-Scheduler][Scheduleautostart] Stop"
		if autoScheduleTimer is not None:
			autoScheduleTimer.schedulestop()

class AutoScheduleTimer:
	instance = None
	def __init__(self, session):
		self.schedulename = "JoyneScan-Scheduler"
		self.config = config.plugins.joynescan
		self.itemtorun = JoyneScan
		self.session = session
		self.scheduletimer = eTimer()
		self.scheduletimer.callback.append(self.ScheduleonTimer)
		self.scheduleactivityTimer = eTimer()
		self.scheduleactivityTimer.timeout.get().append(self.scheduledatedelay)
		self.ScheduleTime = 0
		now = int(time())
		if self.config.schedule.value:
			print"[%s][AutoScheduleTimer] Schedule Enabled at " % self.schedulename, strftime("%c", localtime(now))
			if now > 1546300800: # Tuesday, January 1, 2019 12:00:00 AM
				self.scheduledate()
			else:
				print"[%s][AutoScheduleTimer] STB clock not yet set." % self.schedulename
				self.scheduleactivityTimer.start(36000)
		else:
			print"[%s][AutoScheduleTimer] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now))
			self.scheduleactivityTimer.stop()

		assert AutoScheduleTimer.instance is None, "class AutoScheduleTimer is a singleton class and just one instance of this class is allowed!"
		AutoScheduleTimer.instance = self

	def __onClose(self):
		AutoScheduleTimer.instance = None

	def scheduledatedelay(self):
		self.scheduleactivityTimer.stop()
		self.scheduledate()

	def getScheduleTime(self):
		now = localtime(time())
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, self.config.scheduletime.value[0], self.config.scheduletime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def getScheduleDayOfWeek(self):
		today = self.getToday()
		for i in range(1, 8):
			if self.config.days[(today+i)%7].value:
				return i

	def getToday(self):
		return localtime(time()).tm_wday

	def scheduledate(self, atLeast = 0):
		self.scheduletimer.stop()
		self.ScheduleTime = self.getScheduleTime()
		now = int(time())
		if self.ScheduleTime > 0:
			if self.ScheduleTime < now + atLeast:
				self.ScheduleTime += 86400*self.getScheduleDayOfWeek()
			elif not self.config.days[self.getToday()].value:
				self.ScheduleTime += 86400*self.getScheduleDayOfWeek()
			next = self.ScheduleTime - now
			self.scheduletimer.startLongTimer(next)
		else:
			self.ScheduleTime = -1
		print"[%s][scheduledate] Time set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now))
		self.config.nextscheduletime.value = self.ScheduleTime
		self.config.nextscheduletime.save()
		configfile.save()
		return self.ScheduleTime

	def schedulestop(self):
		self.scheduletimer.stop()

	def ScheduleonTimer(self):
		self.scheduletimer.stop()
		now = int(time())
		wake = self.getScheduleTime()
		atLeast = 0
		if wake - now < 60:
			atLeast = 60
			print"[%s][ScheduleonTimer] onTimer occured at" % self.schedulename, strftime("%c", localtime(now))
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("%s update is about to start.\nDo you want to allow this?") % self.schedulename
				ybox = self.session.openWithCallback(self.doSchedule, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle(_('%s scheduled update') % self.schedulename)
			else:
				self.doSchedule(True)
		self.scheduledate(atLeast)

	def doSchedule(self, answer):
		now = int(time())
		if answer is False:
			if self.config.retrycount.value < 2:
				print"[%s][doSchedule] Schedule delayed." % self.schedulename
				self.config.retrycount.value += 1
				self.ScheduleTime = now + (int(self.config.retry.value) * 60)
				print"[%s][doSchedule] Time now set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now))
				self.scheduletimer.startLongTimer(int(self.config.retry.value) * 60)
			else:
				atLeast = 60
				print"[%s][doSchedule] Enough Retries, delaying till next schedule." % self.schedulename, strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout = 10)
				self.config.retrycount.value = 0
				self.scheduledate(atLeast)
		else:
			self.timer = eTimer()
			self.timer.callback.append(self.runscheduleditem)
			print"[%s][doSchedule] Running Schedule" % self.schedulename, strftime("%c", localtime(now))
			self.timer.start(100, 1)

	def runscheduleditem(self):
		self.session.openWithCallback(self.runscheduleditemCallback, self.itemtorun)

	def runscheduleditemCallback(self):
		from Screens.Standby import Standby, inStandby, TryQuitMainloop, inTryQuitMainloop
		print"[%s][runscheduleditemCallback] inStandby" % self.schedulename, inStandby
		if self.config.schedule.value and wasScheduleTimerWakeup and inStandby and self.config.scheduleshutdown.value and not self.session.nav.getRecordings() and not inTryQuitMainloop:
			print"[%s] Returning to deep standby after scheduled wakeup" % self.schedulename
			self.session.open(TryQuitMainloop, 1)

	def doneConfiguring(self): # called from plugin on save
		now = int(time())
		if self.config.schedule.value:
			if autoScheduleTimer is not None:
				print"[%s][doneConfiguring] Schedule Enabled at" % self.schedulename, strftime("%c", localtime(now))
				autoScheduleTimer.scheduledate()
		else:
			if autoScheduleTimer is not None:
				self.ScheduleTime = 0
				print"[%s][doneConfiguring] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now))
				autoScheduleTimer.schedulestop()
		# scheduletext is not used for anything but could be returned to the calling function to display in the GUI.
		if self.ScheduleTime > 0:
			t = localtime(self.ScheduleTime)
			scheduletext = strftime(_("%a %e %b  %-H:%M"), t)
		else:
			scheduletext = ""
		return scheduletext

