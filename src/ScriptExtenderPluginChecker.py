from enum import Enum, auto
from pathlib import Path
import re
import sys

from PyQt5.QtCore import QCoreApplication, qDebug

if "mobase" not in sys.modules:
    import mock_mobase as mobase


class PluginMessage():
    def __init__(self, pluginPath):
        self._pluginPath = Path(pluginPath)
    
    def successful(self):
        return False
    
    def asMessage(self):
        return self.__tr("{0} existed.").format(self._pluginPath.name)
    
    def __tr(self, str):
        return QCoreApplication.translate("PluginMessage", str)
    
    messageTypes = []
    
    @staticmethod
    def registerMessageType(messageType):
        PluginMessage.messageTypes.append(messageType)
    
    @staticmethod
    def PluginMessageFactory(line):
        for messageType in PluginMessage.messageTypes:
            match = messageType[0].fullmatch(line)
            if match:
                return messageType[1](match)
        return None


class NormalPluginMessage(PluginMessage):
    def __init__(self, match):
        super(NormalPluginMessage, self).__init__(match.group("pluginPath"))
        self.__infoVersion = int(match.group("infoVersion"), 16)
        self.__name = match.group("name")
        self.__version = int(match.group("version"), 16)
        self.__loadStatus = match.group("loadStatus")
    
    def successful(self):
        return self.__loadStatus == "loaded correctly"
    
    def asMessage(self):
        return self.__tr("{0} version {1} ({2}) {3}.").format(self.__name, self.__version, self._pluginPath.name, self.__trLoadStatus())
    
    def __trLoadStatus(self):
        # We need to list the possible options so they get detected as translatable strings.
        loadStatusTranslations = {
            "loaded correctly" : self.__tr("loaded correctly"),
            "reported as incompatible during query" : self.__tr("reported as incompatible during query"),
            "reported as incompatible during load" : self.__tr("reported as incompatible during load"),
            "disabled, fatal error occurred while loading plugin" : self.__tr("disabled, fatal error occurred while loading plugin"),
            "disabled, no name specified" : self.__tr("disabled, no name specified"),
            "disabled, fatal error occurred while checking plugin compatibility" : self.__tr("disabled, fatal error occurred while checking plugin compatibility"),
            "disabled, fatal error occurred while querying plugin" : self.__tr("disabled, fatal error occurred while querying plugin")
        }
        if self.__loadStatus in loadStatusTranslations:
            return loadStatusTranslations[self.__loadStatus]
        else:
            # There's a blacklist of known broken plugins that get excluded, each with their own reason.
            # We aren't translating that.
            return self.__loadStatus
    
    def __tr(self, str):
        return QCoreApplication.translate("NormalPluginMessage", str)

PluginMessage.registerMessageType((re.compile(r"plugin (?P<pluginPath>.+) \((?P<infoVersion>[\dA-Fa-f]{8}) (?P<name>.+) (?P<version>[\dA-Fa-f]{8})\) (?P<loadStatus>.+)\s"), NormalPluginMessage))


class CouldntLoadPluginMessage(PluginMessage):
    def __init__(self, match):
        super(CouldntLoadPluginMessage, self).__init__(match.group("pluginPath"))
        self.__lastError = int(match.group("lastError"))
    
    def successful(self):
        return False
    
    def asMessage(self):
        return self.__tr("Couldn't load {0}. The last error code was {1}.").format(self._pluginPath.name, self.__lastError)
    
    def __tr(self, str):
        return QCoreApplication.translate("CouldntLoadPluginMessage", str)

PluginMessage.registerMessageType((re.compile(r"couldn't load plugin (?P<pluginPath>.+) \(Error (?P<lastError>[-+]?\d+)\)\s"), CouldntLoadPluginMessage))


class NotAPluginMessage(PluginMessage):
    def __init__(self, match):
        super(NotAPluginMessage, self).__init__(match.group("pluginPath"))
    
    def successful(self):
        return False
    
    def asMessage(self):
        return self.__tr("{0} does not appear to be an SKSE plugin.").format(self._pluginPath.name)
    
    def __tr(self, str):
        return QCoreApplication.translate("NotAPluginMessage", str)

PluginMessage.registerMessageType((re.compile(r"plugin (?P<pluginPath>.+) does not appear to be an (?:SK)|(?:F4)|(?:NV)|(?:FO)|(?:OB)SE plugin\s"), NotAPluginMessage))

    
class LogLocation(Enum):
    DOCS = auto()
    INSTALL = auto()

class ScriptExtenderPluginChecker(mobase.IPluginDiagnose):
    
    supportedGames = {
        "Skyrim" : (LogLocation.DOCS, Path("SKSE") / "skse.log"),
        "Skyrim Special Edition" : (LogLocation.DOCS, Path("SKSE") / "skse64.log"),
        "Skyrim VR" : (LogLocation.DOCS, Path("SKSE") / "sksevr.log"),
        #"Enderal" : (LogLocation.DOCS, Path("")),
        "Fallout 4" : (LogLocation.DOCS, Path("F4SE") / "f4se.log"),
        "Oblivion" : (LogLocation.INSTALL, Path("obse.log")),
        "New Vegas" : (LogLocation.INSTALL, Path("nvse.log")),
        "TTW" : (LogLocation.INSTALL, Path("ttw_nvse.log")),
        "Fallout 3" : (LogLocation.INSTALL, Path("fose.log"))
    }
    
    def __init__(self):
        super(ScriptExtenderPluginChecker, self).__init__()
        self.__organizer = None

    def init(self, organizer):
        self.__organizer = organizer
        
        organizer.onFinishedRun(lambda a, b: self._invalidate())
        
        return True

    def name(self):
        return "Script Extender Plugin Load Checker"

    def author(self):
        return "AnyOldName3"

    def description(self):
        return self.__tr("Checks script extender log to see if any plugins failed to load.")

    def version(self):
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.prealpha)

    def isActive(self):
        # This is never called, but it should be.
        return self.__organizer.managedGame().gameName() in self.supportedGames

    def settings(self):
        return []
    
    def activeProblems(self):
        if self.__scanLog():
            return [0]
        else:
            return []
    
    def shortDescription(self, key):
        return self.__tr("Script extender log reports incompatible plugins.")
    
    def fullDescription(self, key):
        pluginList = self.__listBadPluginMessagess()
        pluginListString = "\n• " + ("\n• ".join(pluginList))
        return self.__tr("You have one or more script extender plugins which failed to load. They are:{0}").format(pluginListString)
    
    def hasGuidedFix(self, key):
        return False
    
    def startGuidedFix(self, key):
        pass
    
    def __tr(self, str):
        return QCoreApplication.translate("ScriptExtenderPluginChecker", str)
    
    def __scanLog(self):
        if self.__organizer.managedGame().gameName() not in self.supportedGames:
            return False
        
        base, suffix = self.supportedGames[self.__organizer.managedGame().gameName()]
        
        if base == LogLocation.DOCS:
            base = Path(self.__organizer.managedGame().documentsDirectory().absolutePath())
        elif base == LogLocation.INSTALL:
            base = Path(self.__organizer.managedGame().gameDirectory().absolutePath())
        
        logPath = base / suffix
        
        try:
            with logPath.open('r') as logFile:
                for line in logFile:
                    pluginMessage = PluginMessage.PluginMessageFactory(line)
                    if pluginMessage and not pluginMessage.successful():
                        return True
        except Exception:
            # There's almost certainly just no log yet
            pass
                    
        return False
    
    def __listBadPluginMessagess(self):
        base, suffix = self.supportedGames[self.__organizer.managedGame().gameName()]
        
        if base == LogLocation.DOCS:
            base = Path(self.__organizer.managedGame().documentsDirectory().absolutePath())
        elif base == LogLocation.INSTALL:
            base = Path(self.__organizer.managedGame().gameDirectory().absolutePath())
        
        logPath = base / suffix
                    
        messageList = []
        
        try:
            with logPath.open('r') as logFile:
                for line in logFile:
                    pluginMessage = PluginMessage.PluginMessageFactory(line)
                    if pluginMessage and not pluginMessage.successful():
                        messageList.append(pluginMessage.asMessage())
        except Exception:
            # There's almost certainly just no log yet
            pass
        
        return messageList
                
    
def createPlugin():
    return ScriptExtenderPluginChecker()