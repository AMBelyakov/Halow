cd /d %~dp0

set dirname=%1

del /q/f APP.bin
copy %dirname% APP.bin

set dirname=%dirname:~0,-4%
set dirname=%dirname%_%date:~0,4%%date:~5,2%%date:~8,2%%time:~0,2%%time:~3,2%%time:~6,2%

if not exist bakup md bakup
if not exist bakup\%dirname% md bakup\%dirname%
copy Lst\* bakup\%dirname%\
