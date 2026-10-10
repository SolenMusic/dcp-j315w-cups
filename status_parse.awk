# RFC 2790 device/printer status and error bits; RFC 3805 supply levels.
BEGIN {
  device[1]="other"; device[2]="running"; device[3]="warning"; device[4]="testing"; device[5]="down"
  printer[1]="other"; printer[2]="unknown"; printer[3]="idle"; printer[4]="printing"; printer[5]="warming up"
  split("Low paper|Out of paper|Low ink|Out of ink|Cover open|Paper jam|Offline|Service required|Input tray missing|Output tray missing|Ink cartridge missing|Output nearly full|Output full|Input tray empty|Maintenance overdue", names, /\|/)
}
{
  divider=index($0," = "); if (!divider) next
  oid=substr($0,1,divider-1); value=substr($0,divider+3)
  if (oid==".1.3.6.1.2.1.25.3.2.1.5.1") { sub(/^INTEGER: /,"",value); dev=value }
  if (oid==".1.3.6.1.2.1.25.3.5.1.1.1") { sub(/^INTEGER: /,"",value); state=value }
  if (oid==".1.3.6.1.2.1.25.3.5.1.2.1") { sub(/^Hex-STRING: /,"",value); gsub(/[ \t\r\n]/,"",value); errors=toupper(value) }
  if (oid ~ /^\.1\.3\.6\.1\.2\.1\.43\.11\.1\.1\./) {
    suffix=oid; sub(/^\.1\.3\.6\.1\.2\.1\.43\.11\.1\.1\./,"",suffix)
    split(suffix, parts, /\./); column=parts[1]; key=parts[2] "." parts[3]
    if (column==6) {
      sub(/^STRING: /,"",value); sub(/^"/,"",value); sub(/"$/,"",value)
      gsub(/[[:cntrl:]]/," ",value)
      if (!(key in description)) keys[++supplies]=key
      description[key]=value
    }
    if (column==8) { sub(/^INTEGER: /,"",value); capacity[key]=value }
    if (column==9) { sub(/^INTEGER: /,"",value); level[key]=value }
  }
}
END {
  if (!(dev in device) || !(state in printer) || errors=="" || length(errors)%2 || errors ~ /[^0-9A-F]/) {
    print "ERROR: Incomplete or invalid printer status response." > "/dev/stderr"
    exit 1
  }
  print "Device: " device[dev]
  print "Printer: " printer[state]
  faults=0
  for (i=1; i<=length(errors); i+=2) {
    byte=(index("0123456789ABCDEF",substr(errors,i,1))-1)*16 + index("0123456789ABCDEF",substr(errors,i+1,1))-1
    for (bit=0; bit<8; ++bit) if (int(byte / (2 ^ (7-bit)))%2) {
      number=((i-1)/2)*8+bit
      print "Reported error: " (number<15 ? names[number+1] : "unrecognized flag " number)
      faults++
    }
  }
  if (!faults) print "Reported errors: none"
  if (!supplies) print "Ink levels: unavailable"
  for (i=1; i<=supplies; ++i) {
    key=keys[i]; amount=level[key]
    if (!(key in level) || amount==-1 || amount==-2) text="unknown"
    else if (amount==-3) text="some ink remains; percentage unavailable"
    else if (amount ~ /^[0-9]+$/ && capacity[key] ~ /^[0-9]+$/ && capacity[key]+0>0 && amount+0<=capacity[key]+0)
      text=sprintf("approximately %.0f%%",100*amount/capacity[key])
    else text="percentage unavailable"
    print description[key] ": " text
  }
}
