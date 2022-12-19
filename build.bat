@echo off
rem Windows build script,  can be ran from powershell or via pycharm

set defaultEnvironment=venv10
set scriptFolder=%~p0
set scriptName=%~n0

python %scriptFolder%Utilities\build\%scriptName%.py %defaultEnvironment%
