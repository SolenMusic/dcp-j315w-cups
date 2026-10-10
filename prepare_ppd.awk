# First input: previous queue PPD, or /dev/null. Second input: new template.
# Preserve only choices supported by the new PPD; do not carry old filter paths.
FILENAME == ARGV[1] {
  if ($0 ~ /^\*Default[^:]*:/) {
    key=$1; sub(/^\*Default/, "", key); sub(/:$/, "", key)
    old[key]=$2
  }
  next
}
{
  lines[++count]=$0
  if ($0 ~ /^\*[^ ]+ [^ :]+/) {
    key=$1; sub(/^\*/, "", key)
    value=$2; sub(/[\/:].*$/, "", value)
    choices[key SUBSEP value]=1
  }
}
END {
  for (i=1; i<=count; ++i) {
    line=lines[i]
    if (line ~ /^\*Default[^:]*:/) {
      split(line, fields, /[ \t]+/)
      key=fields[1]; sub(/^\*Default/, "", key); sub(/:$/, "", key)
      if (old[key] != "" && choices[key SUBSEP old[key]])
        line="*Default" key ": " old[key]
    }
    gsub(/@FILTER@/, filter, line)
    print line
  }
}
