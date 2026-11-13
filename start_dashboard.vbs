' Starts the Mining Tracker in the background (no window).
' A shortcut to this file sits in the Windows Startup folder, so it runs at every login.
' The dashboard is then at http://localhost:8501 (only on this computer).

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
python = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.venvs\mining-tracker\Scripts\python.exe"

If Not fso.FileExists(python) Then
    MsgBox "Mining Tracker: Python environment not found." & vbCrLf & _
           "Run run.bat once to set it up.", vbExclamation, "Mining Tracker"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectDir
' 0 = hidden window, False = don't wait for it to finish
shell.Run """" & python & """ -m streamlit run app.py" & _
          " --server.headless true --server.port 8501 --server.address localhost" & _
          " --browser.gatherUsageStats false", 0, False
