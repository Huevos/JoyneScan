from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText

from Screens.Screen import Screen

class JoyneScan_About(Screen):
	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("JoyneScan") + " - " + _("About"))

		self.skinName = ["JoyneScan_About", "Setup" ]

		self["config"] = Label("")

		self["actions"] = ActionMap(["SetupActions", "ColorActions", "MenuActions"],
		{
			"red": self.quit,
			"cancel": self.quit,
			"menu": self.quit,
		}, -2)

		self["key_red"] = StaticText(_("Close"))

		from version import PLUGIN_VERSION

		credits = [
			"JoyneScan %s (c) 2020 \n" % PLUGIN_VERSION,
			"- http://github.com/Huevos\n",
			"- http://github.com/OpenViX\n",
			"- http://github.com/oe-alliance\n",
			"- http://www.world-of-satellite.com\n\n",
			"Application credits:\n",
			"- Huevos (main developer)\n\n",
			"Sources credits (dvbreader):\n",
			"- Sandro Cavazzoni aka skaman (main developer)\n",
			"- Andrew Blackburn aka AndyBlac (main developer)\n",
			"- Peter de Jonge aka PeterJ (developer)\n",
			"- Huevos (developer)\n\n",
		]
		self["config"].setText(''.join(credits))

	def quit(self):
		self.close()
