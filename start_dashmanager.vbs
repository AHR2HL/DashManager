Set WshShell = CreateObject("WScript.Shell")
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")

' Check if DashManager is already running
Set colProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE CommandLine LIKE '%DashManager%app.py%'")

If colProcesses.Count = 0 Then
    ' Not running, start it
    WshShell.CurrentDirectory = "C:\Users\Adam Work\PycharmProjects\DashManager"
    WshShell.Run "pythonw app.py", 0, False
End If
