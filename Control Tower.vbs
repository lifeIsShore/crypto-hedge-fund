Set WshShell = CreateObject("WScript.Shell")
' Set the working directory to the folder where this script is located
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' Run the python UI without showing a console window (0 = hide window)
WshShell.Run "python launcher_ui.py", 0, False
