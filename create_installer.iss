; Inno Setup Script for BluetoothStreamer
; To use this, install Inno Setup from https://jrsoftware.org/isinfo.php
; Then right-click this file and select "Compile"

[Setup]
AppName=BluetoothStreamer
AppVersion=1.0.0
AppPublisher=Your Name
AppPublisherURL=https://github.com/yourusername/bluetoothstreamer
AppSupportURL=https://github.com/yourusername/bluetoothstreamer
AppUpdatesURL=https://github.com/yourusername/bluetoothstreamer
DefaultDirName={autopf}\BluetoothStreamer
DefaultGroupName=BluetoothStreamer
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=BluetoothStreamer-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
Source: "dist\BluetoothStreamer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BluetoothStreamer"; Filename: "{app}\BluetoothStreamer.exe"
Name: "{group}\{cm:UninstallProgram,BluetoothStreamer}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BluetoothStreamer"; Filename: "{app}\BluetoothStreamer.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\BluetoothStreamer"; Filename: "{app}\BluetoothStreamer.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\BluetoothStreamer.exe"; Description: "{cm:LaunchProgram,BluetoothStreamer}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Check if Python is required (for future versions that might need it)
  // For now, the executable is standalone, so no check needed
end;

