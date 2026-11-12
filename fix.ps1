$files = @('.specify/scripts/bash/check-prerequisites.sh', '.specify/scripts/bash/common.sh')
foreach($f in $files){
  $content = [System.IO.File]::ReadAllText($f)
  $content = $content.Replace("`r`n", "`n").Replace("`r", "`n")
  [System.IO.File]::WriteAllText($f, $content)
}
