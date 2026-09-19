Set WshShell = CreateObject("WScript.Shell")

' Define absolute paths
Dim projectPath
projectPath = "c:\Users\Markuhhh\Desktop\Jr\Projects\Projects\Deeks"
Dim logPath
logPath = projectPath & "\logs\deeks_startup.log"

' Create the logs directory if it doesn't exist
Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FolderExists(projectPath & "\logs") Then
    fso.CreateFolder(projectPath & "\logs")
End If

' Run python via cmd so we can redirect output to a log file, keeping the window completely hidden (0)
' We use /c and cd to the project path first to ensure all relative imports in Python work correctly.
' We use the global python if venv isn't found, but try to use venv first.
Dim pythonCmd
pythonCmd = "python"
If fso.FileExists(projectPath & "\venv\Scripts\python.exe") Then
    pythonCmd = projectPath & "\venv\Scripts\python.exe"
End If

Dim cmd
cmd = "cmd.exe /c cd /d """ & projectPath & """ && """ & pythonCmd & """ main.py >> """ & logPath & """ 2>&1"

WshShell.Run cmd, 0
Set WshShell = Nothing
