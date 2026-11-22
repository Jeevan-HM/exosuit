#!/usr/bin/env python3
"""
Subject-Specific CSV to HDF5 Converter
======================================
Converts CSV files from New_Collected_Data/Raw_data/<Subject>/ to an organized,
hierarchical HDF5 file at New_Collected_Data/HDF5/<Subject>/<Subject>_Trials_All_Organized.h5.

This script processes a single subject at a time to avoid memory overload
and keeps the workspace clean and simple.

Usage:
  python csv_to_hdf5.py [--subject SUBJECT_NAME]
"""

import os
import sys
import re
import json
from pathlib import Path
import numpy as np
import pandas as pd
import h5py

def parse_emg_array(s):
    """
    Parse a string containing an array of EMG samples into a list of floats.
    Example: "[1.23e-05, 2.34e-05, ...]" -> list of floats
             "[np.float64(1.23e-05), ...]" -> list of floats
    """
    s = str(s).strip()
    if not s or s == '[]' or s == 'nan':
        return None
    try:
        # Remove brackets
        s = s.strip('[]').strip()
        if not s:
            return None
        # Remove 'np.float64()' wrapper if present
        s = re.sub(r'np\.float64\((.*?)\)', r'\1', s)
        # Parse values
        return [float(p.strip()) for p in s.split(',') if p.strip()]
    except Exception:
        return None

def extract_trial_info(filename, subject_name):
    """
    Extract incline, speed, controller type, and trial number from filename.
    Format: Raw_<Subject>_<Controller>_inc<Incline>_spd<Speed>_<TrialNum>.csv
    """
    name = Path(filename).stem
    if not name.startswith("Raw_"):
        return None

    # Extract incline and speed
    inc_match = re.search(r'inc(\d+)', name)
    spd_match = re.search(r'spd([0-9p.]+)', name)
    if not inc_match or not spd_match:
        return None

    incline = int(inc_match.group(1))
    speed_str = spd_match.group(1).replace('p', '.')

    # Extract trial number (typically at the end)
    num_match = re.search(r'_(\d+)$', name)
    if not num_match:
        return None
    trial_num = int(num_match.group(1))

    # Identify controller type
    name_upper = name.upper()
    if 'EXOACTIVE_RL' in name_upper or 'ACTIVE_RL' in name_upper:
        controller = 'active_rl'
    elif 'BASELINE' in name_upper:
        controller = 'baseline'
    elif 'EXOINACTIVE' in name_upper or 'INACTIVE' in name_upper:
        controller = 'inactive'
    elif 'NOEXO' in name_upper:
        controller = 'noexo'
    else:
        return None

    condition_key = f'inc{incline}_spd{speed_str}'

    return {
        'incline': incline,
        'speed': speed_str,
        'controller': controller,
        'trial_num': trial_num,
        'condition_key': condition_key
    }

def convert_csv_to_data_dict(csv_path):
    """
    Read CSV file and parse into a dictionary of 1D (Time, HS_Flag, Knee_Angle) 
    and 2D (EMG signals) numpy arrays.
    """
    df = pd.read_csv(csv_path)

    required_cols = ['Time', 'HS_Flag', 'Knee_Angle']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    data = {
        'Time': pd.to_numeric(df['Time'], errors='coerce').values,
        'HS_Flag': pd.to_numeric(df['HS_Flag'], errors='coerce').fillna(0).astype(np.int64).values,
        'Knee_Angle': pd.to_numeric(df['Knee_Angle'], errors='coerce').values
    }

    # Process EMG columns
    emg_cols = ['EMG_VL', 'EMG_RF', 'EMG_BF', 'EMG_ST']
    for col in emg_cols:
        if col in df.columns:
            # Parse string arrays into lists
            parsed_rows = [parse_emg_array(val) for val in df[col].values]
            
            # Determine packet size (usually 100 samples)
            sizes = [len(r) for r in parsed_rows if r is not None]
            common_size = max(sizes) if sizes else 100
            
            # Construct 2D array: (num_rows, samples_per_row)
            emg_2d = np.full((len(df), common_size), np.nan, dtype=np.float64)
            for i, row_vals in enumerate(parsed_rows):
                if row_vals is not None and len(row_vals) > 0:
                    length_to_copy = min(len(row_vals), common_size)
                    emg_2d[i, :length_to_copy] = row_vals[:length_to_copy]
            
            data[col] = emg_2d
        else:
            data[col] = None

    return data

def main():
    raw_data_dir = Path("New_Collected_Data/Raw_data")
    if not raw_data_dir.exists():
        print(f"Error: Raw data directory not found at {raw_data_dir}")
        sys.exit(1)

    # Scan for available subjects that have CSV files
    subjects = sorted([
        d.name for d in raw_data_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and list(d.glob("*.csv"))
    ])

    if not subjects:
        print("No subject directories with CSV files found in New_Collected_Data/Raw_data.")
        sys.exit(1)

    selected_subject = None

    # Check CLI arguments
    if len(sys.argv) > 2 and sys.argv[1] == '--subject':
        cli_subject = sys.argv[2]
        if cli_subject in subjects:
            selected_subject = cli_subject
        else:
            print(f"Subject '{cli_subject}' not found. Available subjects: {', '.join(subjects)}")
            sys.exit(1)

    # Interactive prompt if not selected via CLI
    if not selected_subject:
        print("\nAvailable Subject Folders:")
        for idx, subj in enumerate(subjects, 1):
            num_csvs = len(list((raw_data_dir / subj).glob("*.csv")))
            print(f"  {idx}. {subj} ({num_csvs} CSV files)")
        
        try:
            choice = input(f"\nSelect subject [1-{len(subjects)}] or enter subject folder name: ").strip()
            if choice.isdigit():
                val = int(choice)
                if 1 <= val <= len(subjects):
                    selected_subject = subjects[val - 1]
            elif choice in subjects:
                selected_subject = choice
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

    if not selected_subject:
        print("Invalid selection. Exiting.")
        sys.exit(1)

    subject_dir = raw_data_dir / selected_subject
    csv_files = sorted(list(subject_dir.glob("*.csv")))
    
    print(f"\nProcessing Subject: {selected_subject}")
    print(f"Found {len(csv_files)} CSV files to convert.")

    # Match and organize files
    trials_to_convert = []
    file_mapping = []

    for csv_file in csv_files:
        info = extract_trial_info(csv_file.name, selected_subject)
        if info:
            trials_to_convert.append((csv_file, info))
            file_mapping.append({
                'csv_file': csv_file.name,
                'condition': info['condition_key'],
                'controller': info['controller'],
                'trial_num': info['trial_num'],
                'incline': info['incline'],
                'speed': info['speed']
            })

    if not trials_to_convert:
        print("No CSV files matched the expected trial patterns. Filenames must match:")
        print("Raw_<SubjectName>_<Controller>_inc<Incline>_spd<Speed>_<TrialNum>.csv")
        sys.exit(1)

    # Prepare output path
    output_dir = Path("New_Collected_Data/HDF5") / selected_subject
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{selected_subject}_Trials_All_Organized.h5"

    print(f"Output File: {output_file}\n")

    # Perform conversion
    converted_count = 0
    with h5py.File(str(output_file), 'w') as h5f:
        # Store global file metadata
        h5f.attrs['subject'] = selected_subject
        h5f.attrs['description'] = f'Organized trial data for subject {selected_subject}'
        h5f.attrs['num_trials'] = len(trials_to_convert)

        # Write file mapping metadata dataset
        meta_group = h5f.create_group('metadata')
        meta_group.create_dataset(
            'file_mapping',
            data=json.dumps(file_mapping, indent=2),
            dtype=h5py.string_dtype(encoding='utf-8')
        )

        for i, (csv_path, info) in enumerate(trials_to_convert, 1):
            print(f"[{i}/{len(trials_to_convert)}] Converting: {csv_path.name}")
            try:
                # Load and parse CSV
                data = convert_csv_to_data_dict(csv_path)

                # Set up groups in HDF5 hierarchy
                condition_key = info['condition_key']
                controller = info['controller']
                trial_num = info['trial_num']
                
                group_path = f'/conditions/{condition_key}/{controller}/trial_{trial_num}'
                trial_group = h5f.create_group(group_path)
                data_group = trial_group.create_group('data')

                # Add group-level attributes
                trial_group.attrs['csv_source'] = csv_path.name
                trial_group.attrs['incline'] = info['incline']
                trial_group.attrs['speed'] = info['speed']
                trial_group.attrs['controller'] = controller
                trial_group.attrs['trial_number'] = trial_num

                # Write datasets with gzip compression
                for col_name, col_data in data.items():
                    if col_data is not None:
                        data_group.create_dataset(
                            col_name,
                            data=col_data,
                            dtype=col_data.dtype,
                            compression='gzip',
                            compression_opts=4,
                            chunks=True
                        )
                converted_count += 1

            except Exception as e:
                print(f"  ERROR converting {csv_path.name}: {e}")

    print(f"\nSuccess! Successfully converted {converted_count}/{len(trials_to_convert)} files.")
    print(f"Organized HDF5 file saved at: {output_file}")
    print("\nMATLAB Load Example:")
    print(f"  Time = h5read('{output_file}', '/conditions/inc0_spd0.8/active_rl/trial_1/data/Time');")
    print(f"  EMG_VL = h5read('{output_file}', '/conditions/inc0_spd0.8/active_rl/trial_1/data/EMG_VL');")

if __name__ == '__main__':
    main()
