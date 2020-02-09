# for localized messages
from . import _

from Components.ActionMap import ActionMap
from Components.config import config, getConfigListEntry, configfile
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Sources.StaticText import StaticText

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from about import JoyneScan_About
from providers import PROVIDERS

from enigma import eTimer

from time import localtime, time, strftime, mktime

class JoyneScan(): # the downloader
	def __init__(self, session, args = None):
		pass


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
		self.list.append(getConfigListEntry(_("Clear before scan"), self.config.clearallservices, _('If you select "yes" stored channels at the same orbital position will be deleted before starting the current search. Note: if you are scanning more than one provider this must be set to "no".')))
		self.list.append(getConfigListEntry(_("Show in extensions menu"), self.config.extensions, _('When enabled, this allows you start a Joyne update from the extensions list.')))

		self.list.append(getConfigListEntry(_("Scheduled fetch"), self.config.schedule, _("Set up a task scheduler to periodically update Joyne data.")))
		if self.config.schedule.value:
			self.list.append(getConfigListEntry(indent + _("Schedule time of day"), self.config.scheduletime, _("Set the time of day to run JoyneScan.")))
			self.list.append(getConfigListEntry(indent + _("Schedule days of the week"), self.config.dayscreen, _("Press OK to select which days to run JoyneScan.")))
			self.list.append(getConfigListEntry(indent + _("Schedule wake from deep standby"), self.config.schedulewakefromdeep, _("If the receiver is in 'Deep Standby' when the schedule is due wake it up to run JoyneScan.")))
			if self.config.schedulewakefromdeep.value:
				self.list.append(getConfigListEntry(indent + _("Schedule return to deep standby"), self.config.scheduleshutdown, _("If the receiver was woken from 'Deep Standby' and is currently in 'Standby' and no recordings are in progress return it to 'Deep Standby' once the import has completed.")))

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
		#self.session.openWithCallback(self.joynescanCallback, JoyneScan, {})

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

