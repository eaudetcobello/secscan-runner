#!/bin/bash

output_dir="output"

if [[ $1 ]]; then
  output_dir=$1
fi

for dir in "$output_dir"/*; do
  echo "Processing directory: $dir"

  # Check if there are any .report files in the directory
  shopt -s nullglob  # Ensure the loop does not execute if no .report files exist
  report_files=("$dir"/*.report)
  shopt -u nullglob  # Restore default behavior

  if [[ ${#report_files[@]} -eq 0 ]]; then
    echo "No .report files found in $dir, skipping..."
    continue
  fi

  for file in "${report_files[@]}"; do
    echo "Processing file: $file"
    
    filename=$(basename "$file" .report)  # Extract filename without extension
    output_csv="$dir/${filename}.csv"

    # Write the header row to the CSV file
    echo -e "\ufeffVulnerability ID,Project Name,Version,Severity,Filename" > "$output_csv"

    # Append data to the CSV file
    jq --raw-output -r --arg filename "$filename" '
      .versionDetailedRiskVulnerabilities[0].detailedRiskVulnerabilities[]
      | select(.severity == "HIGH" or .severity == "CRITICAL")
      | [ .vulnerabilityId, .producerProjectName, .producerVersion, .severity, $filename ]
      | @csv' "$file" >> "$output_csv"
  done
done

{
  # Print header only once
  head -n 1 "$(find $output_dir -name '*.csv' | head -n 1)"

  # Append all CSVs without their headers
  find $output_dir -name '*.csv' | while read file; do
    tail -n +2 "$file"
  done
} > combined.csv

# | select(.producerProjectName | IN("GNU C Library", "PCRE2", "Perl", "XZ Utils", "zlib", "GNU tar", "zstd") | not)
