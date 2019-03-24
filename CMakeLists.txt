# Version chosen arbitrarily
CMAKE_MINIMUM_REQUIRED(VERSION 3.0)

PROJECT(ScriptExtenderPluginChecker LANGUAGES NONE)

# Value passed from modorganizer-umbrella
SET(DEPENDENCIES_DIR CACHE PATH "")

LIST(APPEND CMAKE_PREFIX_PATH ${QT_ROOT}/lib/cmake)

ADD_SUBDIRECTORY(src)
