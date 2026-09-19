Set WshShell = CreateObject("WScript.Shell")
' Get the directory of this VBScript to locate the powershell script
Dim scriptDir
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Run the PowerShell script completely hidden (0)
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptDir & "\startup.ps1""", 0, False

Set WshShell = Nothing
