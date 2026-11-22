%% select_stable_cycles.m
% Select N gait cycles with least standard deviation per muscle
%
% Features:
%   - Load processed trial .mat file with EMG cycles
%   - Calculate cycle-by-cycle standard deviation for each muscle
%   - Choose: use all cycles OR select N best cycles
%   - Save selected cycles to new .mat file
%
% USAGE:
%   1. Run script
%   2. Select processed trial .mat file
%   3. Choose processing mode (all or N cycles)
%   4. Select output file name
%   5. Save processed data with only selected cycles

clear all; close all; clc;

fprintf('="*80\n');
fprintf('STABLE CYCLE SELECTOR - Select N Best Cycles Per Muscle\n');
fprintf('="*80\n\n');

%% ===== STEP 1: SELECT TRIAL FILE =====

fprintf('Select a processed trial .mat file:\n');
[filename, filepath] = uigetfile('*.mat', ...
    'Select processed trial file', ...
    './');

if ~filename
    error('No file selected. Exiting.');
end

full_path = fullfile(filepath, filename);
fprintf('Loading: %s\n\n', filename);

% Load data
data = load(full_path, 'emg_cycles', 'knee_cycles', 'pgc_emg', 'pgc_knee', 'n_cycles');
emg_cycles = data.emg_cycles;
n_cycles = data.n_cycles;

fprintf('Total cycles in file: %d\n\n', n_cycles);

%% ===== STEP 2: CHOOSE PROCESSING MODE =====

fprintf('Select processing mode:\n');
fprintf('  1: Use ALL cycles\n');
fprintf('  2: Select N best cycles (lowest std dev)\n\n');

user_choice = input('Enter choice (1 or 2): ');

if user_choice == 1
    % Use all cycles
    use_all_cycles = true;
    n_selected = n_cycles;
    fprintf('\nProcessing ALL %d cycles\n', n_cycles);
    selected_indices = 1:n_cycles;
    
elseif user_choice == 2
    % Select N best cycles
    use_all_cycles = false;
    fprintf('\nEnter number of cycles to select (< %d): ', n_cycles);
    n_selected = input('');
    
    if n_selected >= n_cycles || n_selected < 1
        error('Invalid number of cycles. Must be between 1 and %d.', n_cycles - 1);
    end
    
    fprintf('\nCalculating cycle-by-cycle standard deviation...\n\n');
    
    % Calculate std dev for each cycle of each muscle
    muscles = {'VL', 'RF', 'BF', 'ST'};
    cycle_std_per_muscle = struct();
    
    for m = 1:4
        muscle = muscles{m};
        muscle_cycles = cell2mat(emg_cycles.(muscle)');  % Convert to matrix: samples x cycles
        
        % Calculate std dev for each cycle (column)
        cycle_std_per_muscle.(muscle) = std(muscle_cycles, 0, 1);  % std across samples for each cycle
        
        fprintf('%s - Cycle stds: min=%.2e, max=%.2e, mean=%.2e\n', ...
            muscle, min(cycle_std_per_muscle.(muscle)), max(cycle_std_per_muscle.(muscle)), ...
            mean(cycle_std_per_muscle.(muscle)));
    end
    
    % Calculate combined metric: average std dev across all 4 muscles for each cycle
    combined_std = (cycle_std_per_muscle.VL + cycle_std_per_muscle.RF + ...
                    cycle_std_per_muscle.BF + cycle_std_per_muscle.ST) / 4;
    
    % Sort and find N best cycles (lowest combined std dev)
    [~, sorted_indices] = sort(combined_std, 'ascend');
    selected_indices = sort(sorted_indices(1:n_selected));
    
    fprintf('\nSelected %d cycles with lowest combined std dev\n', n_selected);
    fprintf('Selected cycle indices: %s\n\n', mat2str(selected_indices));
    
else
    error('Invalid choice. Enter 1 or 2.');
end

%% ===== STEP 3: EXTRACT SELECTED CYCLES =====

fprintf('\nExtracting selected cycles...\n');

emg_cycles = struct();
knee_cycles = struct();
muscles = {'VL', 'RF', 'BF', 'ST'};

for m = 1:4
    muscle = muscles{m};
    
    % Extract selected cycles for EMG
    emg_all = data.emg_cycles.(muscle);
    emg_cycles.(muscle) = emg_all(selected_indices);
    
    % Extract selected cycles for knee (if available)
    if isfield(data, 'knee_cycles') && isfield(data.knee_cycles, muscle)
        knee_all = data.knee_cycles.(muscle);
        knee_cycles.(muscle) = knee_all(selected_indices);
    end
end

%% ===== STEP 4: SAVE TO NEW MAT FILE =====

mvc_VL = 0.000310726102982913*0.1; 
mvc_RF = 0.00037249038207918996*0.1;  
mvc_BF = 6.007187876334844e-05*0.5; 
mvc_ST = 4.091189501939166e-05*0.5;   


fprintf('\nChoose output file name:\n');
[outfile, outpath] = uiputfile('*.mat', ...
    'Save selected cycles as:', ...
    fullfile(filepath, sprintf('%s_selected_%dcycles.mat', filename(1:end-4), n_selected)));

if ~outfile
    fprintf('Save cancelled.\n');
    return;
end

output_path = fullfile(outpath, outfile);

% Prepare data to save
pgc_emg = data.pgc_emg;
pgc_knee = data.pgc_knee;
n_cycles_selected = n_selected;

% Save to .mat file
fprintf('\nSaving to: %s\n', outfile);
save(output_path, 'emg_cycles', 'knee_cycles', ...
    'pgc_emg', 'pgc_knee', 'n_cycles', 'n_cycles_selected', 'selected_indices', ...
    'use_all_cycles', '-v7.3');

fprintf('SUCCESS: Saved %d cycles to %s\n', n_cycles_selected, outfile);

%% ===== STEP 5: SUMMARY STATISTICS =====

fprintf('\n');
fprintf('="*80\n');
fprintf('SUMMARY\n');
fprintf('="*80\n');
fprintf('Original cycles:     %d\n', n_cycles);
fprintf('Selected cycles:     %d\n', n_cycles_selected);
fprintf('Processing mode:     %s\n', ternary(use_all_cycles, 'All cycles', sprintf('%d best cycles', n_selected)));
fprintf('Output file:         %s\n', outfile);
fprintf('="*80\n');

%% ===== UTILITY FUNCTION =====

function result = ternary(condition, true_val, false_val)
    if condition
        result = true_val;
    else
        result = false_val;
    end
end
