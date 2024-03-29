# for localized messages
from . import _

description = _("Scans for Joyne services and creates a bouquet")

from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigNumber, NoSave, ConfigClock, ConfigEnableDisable, ConfigSubDict
from Components.NimManager import nimmanager
from Plugins.Plugin import PluginDescriptor
from Tools.BoundFunction import boundFunction

from .joynescan import Scheduleautostart, JoyneScan, JoyneScan_Setup
from .providers import PROVIDERS

config.plugins.joynescan = ConfigSubsection()
config.plugins.joynescan.provider = ConfigSelection(default = "Joyne_NL", choices = [(x, PROVIDERS[x]["name"]) for x in sorted(PROVIDERS.keys())])
config.plugins.joynescan.extensions = ConfigYesNo(default = False)

# start: joynescan.schedule
config.plugins.joynescan.schedule = ConfigYesNo(default = False)
config.plugins.joynescan.scheduletime = ConfigClock(default = 0) # 1:00
config.plugins.joynescan.retry = ConfigNumber(default = 30)
config.plugins.joynescan.retrycount = NoSave(ConfigNumber(default = 0))
config.plugins.joynescan.nextscheduletime = ConfigNumber(default = 0)
config.plugins.joynescan.schedulewakefromdeep = ConfigYesNo(default = True)
config.plugins.joynescan.scheduleshutdown = ConfigYesNo(default = True)
config.plugins.joynescan.dayscreen = ConfigSelection(choices = [("1", _("Press OK"))], default = "1")
config.plugins.joynescan.days = ConfigSubDict()
for i in range(7):
	config.plugins.joynescan.days[i] = ConfigEnableDisable(default = True)
# end: joynescan.schedule

config.plugins.joynescan.extra_debug = ConfigYesNo(default = False)
config.plugins.joynescan.sync_with_known_tps = ConfigYesNo(default = True)
config.plugins.joynescan.force_service_name = ConfigYesNo(default = False)


def startdownload(session, **kwargs): # Called from extensions menu if this option is active
	session.open(JoyneScan)

def JoyneScanStart(menuid, **kwargs): # Menu position of plugin setup screen
	if menuid == "scan":
		return [(_("JoyneScan"), JoyneScanMain, "JoyneScan_Setup", 11, True)]
	return []

def JoyneScanMain(session, close=None, **kwargs): # calls setup screen
	session.openWithCallback(boundFunction(JoyneScanCallback, close), JoyneScan_Setup)

def JoyneScanCallback(close=None, answer=None): # Called on exiting setup screen. Should force a recursive close on a succsssful scan.
	if close and answer:
		close(True)

def JoyneScanWakeupTime(): # Called on shutdown (going into deep standby) to tell the box when to wake from deep
	print("[JoyneScan] next wake up due %d" % (config.plugins.joynescan.schedule.value and config.plugins.joynescan.schedulewakefromdeep.value and config.plugins.joynescan.nextscheduletime.value > 0 and config.plugins.joynescan.nextscheduletime.value or -1))
	return config.plugins.joynescan.schedule.value and config.plugins.joynescan.schedulewakefromdeep.value and config.plugins.joynescan.nextscheduletime.value > 0 and config.plugins.joynescan.nextscheduletime.value or -1

def Plugins(**kwargs):
	plist = []
	if nimmanager.hasNimType("DVB-S"):
		plist.append( PluginDescriptor(name=_("JoyneScan"), description=description, where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc=JoyneScanStart) )
		plist.append(PluginDescriptor(name="JoyneScanScheduler", where=[ PluginDescriptor.WHERE_AUTOSTART, PluginDescriptor.WHERE_SESSIONSTART ], fnc=Scheduleautostart, wakeupfnc=JoyneScanWakeupTime, needsRestart=True))
		if config.plugins.joynescan.extensions.getValue():
			plist.append(PluginDescriptor(name=_("JoyneScan"), description=description, where = PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=startdownload, needsRestart=True))
	return plist
