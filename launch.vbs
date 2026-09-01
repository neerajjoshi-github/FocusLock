Option Explicit
On Error Resume Next

Dim service, root, task, fso, shell, exe

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
exe = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "FocusLock.exe")

Set service = CreateObject("Schedule.Service")
service.Connect
Set root = service.GetFolder("\")
Set task = root.GetTask("FocusLock")

If Err.Number = 0 Then
    If Not task Is Nothing Then
        task.Run Null
        If Err.Number = 0 Then
            WScript.Quit 0
        End If
    End If
End If

Err.Clear
shell.Run """" & exe & """", 1, False
