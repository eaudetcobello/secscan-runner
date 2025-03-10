for dir in output/*; do
  echo "Processing $dir"
  for file in $dir/*.report; do
    echo "Processing $file"
    filename=$(basename "$file" .report)  # Extract filename without extension
    # Define CSV output file
    output_csv="$dir/${filename}.csv"

    # Write the header row to the file
    echo -e "\ufeffVulnerability ID,Project Name,Version,Severity,Filename" > "$output_csv"

    # Append data to the CSV file
    jq --raw-output -r --arg filename "$filename" '
      .versionDetailedRiskVulnerabilities[0].detailedRiskVulnerabilities[]
      | select(.severity == "HIGH" or .severity == "CRITICAL")
      | select(.producerProjectName | IN("GNU C Library", "PCRE2", "Perl", "XZ Utils", "zlib", "GNU tar", "zstd") | not)
      | [ .vulnerabilityId, .producerProjectName, .producerVersion, .severity, $filename ]
      | @csv' "$file" >> "$output_csv"
  done
done
