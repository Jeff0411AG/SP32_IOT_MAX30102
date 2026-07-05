param(
  [string]$Fqbn = "esp32:esp32:esp32",
  [string]$Port = "",
  [switch]$Upload
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$cli = Join-Path $root "tools\arduino-cli\arduino-cli.exe"
$sketchName = "Sensor_de_frecuencia_Cardiaca_GSM"
$sketchDir = Join-Path $root "firmware\$sketchName"
$outDir = Join-Path $root ".arduino-build\output"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

& $cli compile --fqbn $Fqbn --additional-urls "https://espressif.github.io/arduino-esp32/package_esp32_index.json" --output-dir $outDir $sketchDir

if ($Upload)
{
  if ([string]::IsNullOrWhiteSpace($Port))
  {
    throw "Debe indicar -Port para subir a la placa."
  }

  & $cli upload -p $Port --fqbn $Fqbn --input-dir $outDir $sketchDir
}
