%% process_raw_data.m (HDF5 Version - Manual Trial Selection)
%  Processes HDF5 files from organized trials
%
%  For each gait cycle (Heel Strike to Heel Strike):
%    - Extracts Knee Angle, normalized to 0-100% GC (100 points)
%    - Extracts raw EMG per muscle (concatenated 100-sample packets)
%    - Calls emg_processing() to bandpass, envelope, resample to 1001 pts
%    - Plots RAW envelopes only (no MVC normalization; done downstream)
%
%  OUTPUTS:
%    1. Plots: Knee angle & normalized EMG envelopes (mean ± SD)
%    2. .mat file: Processed EMG data (NOT MVC-normalized) for comparison
%       saved as: Processed_{condition}_{controller}_trial{num}.mat
%
%  KEY FEATURES:
%    - Manual trial selection with UI dialog
%    - EMG data saved RAW (un-normalized) for flexible comparisons
%    - No MVC handling here; normalization happens in the subject-folder analysis
%    - File names encode trial metadata for easy identification
%
% =========================================================================

%% ===== STEP 0: MANUAL TRIAL SELECTION =====

% >>> SET SUBJECT ONCE <<< everything below (input .h5 and output folder) derives from it.
subject = 'Rachitha';

h5_file    = sprintf('New_Collected_Data/HDF5/%s/%s_Trials_All_Organized.h5', subject, subject);
output_dir = sprintf('Offline_Processed_Data/%s', subject);
if ~exist(output_dir, 'dir'), mkdir(output_dir); end

% Define available trials with metadata
available_trials = {
    'inc0_spd0.8', 'active_rl', 1;
    'inc0_spd0.8', 'active_rl', 2;
    'inc0_spd0.8', 'inactive', 1;
    'inc0_spd0.8', 'noexo', 1;
    'inc0_spd1.2', 'active_rl', 1;
    'inc0_spd1.2', 'active_rl', 2;
    'inc0_spd1.2', 'baseline', 1;
    'inc0_spd1.2', 'inactive', 1;
    'inc0_spd1.2', 'noexo', 1;
    'inc5_spd0.8', 'active_rl', 1;
    'inc5_spd0.8', 'active_rl', 2;
    'inc5_spd0.8', 'inactive', 1;
    'inc5_spd0.8', 'noexo', 1;
    'inc5_spd1.2', 'active_rl', 1;
    'inc5_spd1.2', 'active_rl', 2;
    'inc5_spd1.2', 'inactive', 1;
    'inc5_spd1.2', 'noexo', 1;
};

% Ask user: Single trial or batch process all?
choice = questdlg('Process mode:', 'Trial Processing', ...
    'Single Trial', 'Process All (Batch)', 'Single Trial');

if isempty(choice)
    error('User cancelled. Exiting.');
end

if strcmp(choice, 'Process All (Batch)')
    % ===== BATCH PROCESS ALL TRIALS =====
    % (No MVC here — envelopes are saved raw; normalization is applied downstream.)

    fprintf('\n');
    fprintf('%s\n', repmat('=', 1, 80));
    fprintf('BATCH PROCESSING ALL 17 TRIALS\n');
    fprintf('%s\n', repmat('=', 1, 80));
    fprintf('\n');
    
    num_trials = size(available_trials, 1);
    successful = 0;
    failed = 0;
    
    for trial_idx = 1:num_trials
        condition = available_trials{trial_idx, 1};
        controller = available_trials{trial_idx, 2};
        trial_num = available_trials{trial_idx, 3};
        
        fprintf('\n[%d/%d] Processing: %s - %s - Trial %d\n', ...
            trial_idx, num_trials, condition, controller, trial_num);
        fprintf('%s\n', repmat('-', 1, 80));
        
        try
            % Extract trial info
            condition = available_trials{trial_idx, 1};
            controller = available_trials{trial_idx, 2};
            trial_num = available_trials{trial_idx, 3};
            
            % Build HDF5 path
            h5_path = sprintf('/conditions/%s/%s/trial_%d/data', condition, controller, trial_num);
            
            % Read data
            Time = h5read(h5_file, [h5_path '/Time']);
            HS_Flag = h5read(h5_file, [h5_path '/HS_Flag']);
            Knee_Angle = h5read(h5_file, [h5_path '/Knee_Angle']);
            
            EMG_VL_2d = h5read(h5_file, [h5_path '/EMG_VL']);
            EMG_RF_2d = h5read(h5_file, [h5_path '/EMG_RF']);
            EMG_BF_2d = h5read(h5_file, [h5_path '/EMG_BF']);
            EMG_ST_2d = h5read(h5_file, [h5_path '/EMG_ST']);
            
            % Convert to cell arrays
            n_rows = length(Time);
            EMG_VL_cells = cell(n_rows, 1);
            EMG_RF_cells = cell(n_rows, 1);
            EMG_BF_cells = cell(n_rows, 1);
            EMG_ST_cells = cell(n_rows, 1);
            
            for i = 1:n_rows
                EMG_VL_cells{i} = EMG_VL_2d(:, i);
                EMG_RF_cells{i} = EMG_RF_2d(:, i);
                EMG_BF_cells{i} = EMG_BF_2d(:, i);
                EMG_ST_cells{i} = EMG_ST_2d(:, i);
            end
            
            T = table(Time, HS_Flag, Knee_Angle, EMG_VL_cells, EMG_RF_cells, EMG_BF_cells, EMG_ST_cells);
            T.Properties.VariableNames = {'Time', 'HS_Flag', 'Knee_Angle', 'EMG_VL', 'EMG_RF', 'EMG_BF', 'EMG_ST'};
            
            % Find gait cycles
            hs_vec = T.HS_Flag;
            hs_indices = find(hs_vec == 1);
            n_cycles = length(hs_indices) - 1;
            
            if n_cycles < 1
                fprintf('    ✗ No heel strikes found\n');
                failed = failed + 1;
                continue;
            end
            
            % Initialize arrays
            pgc_knee = linspace(0, 100, 100)';
            pgc_emg = linspace(0, 100, 1001)';
            
            knee_cycles = cell(n_cycles, 1);
            emg_cycles.VL = cell(n_cycles, 1);
            emg_cycles.RF = cell(n_cycles, 1);
            emg_cycles.BF = cell(n_cycles, 1);
            emg_cycles.ST = cell(n_cycles, 1);
            
            % Process each cycle
            for c = 1:n_cycles
                idx_start = hs_indices(c);
                idx_end = hs_indices(c + 1) - 1;
                rows = idx_start:idx_end;
                
                % Knee angle
                knee_raw = T.Knee_Angle(rows);
                knee_raw = knee_raw(~isnan(knee_raw));
                if length(knee_raw) >= 2
                    x_knee = linspace(0, 100, length(knee_raw));
                    knee_norm = interp1(x_knee, knee_raw, pgc_knee, 'spline');
                else
                    knee_norm = nan(100, 1);
                end
                knee_cycles{c} = knee_norm;
                
                % EMG processing
                get_emg = @(T, rows, muscle) get_emg_from_cells(T, rows, muscle);
                
                raw_VL = get_emg(T, rows, 'VL');
                raw_RF = get_emg(T, rows, 'RF');
                raw_BF = get_emg(T, rows, 'BF');
                raw_ST = get_emg(T, rows, 'ST');
                
                raw_VL = remove_duplicate_packets(raw_VL, 100);
                raw_RF = remove_duplicate_packets(raw_RF, 100);
                raw_BF = remove_duplicate_packets(raw_BF, 100);
                raw_ST = remove_duplicate_packets(raw_ST, 100);
                
                if length(raw_VL) >= 10
                    [emg_cycles.VL{c}, ~] = emg_processing(raw_VL, 1);
                else
                    emg_cycles.VL{c} = nan(1001, 1);
                end
                if length(raw_RF) >= 10
                    [emg_cycles.RF{c}, ~] = emg_processing(raw_RF, 1);
                else
                    emg_cycles.RF{c} = nan(1001, 1);
                end
                if length(raw_BF) >= 10
                    [emg_cycles.BF{c}, ~] = emg_processing(raw_BF, 1);
                else
                    emg_cycles.BF{c} = nan(1001, 1);
                end
                if length(raw_ST) >= 10
                    [emg_cycles.ST{c}, ~] = emg_processing(raw_ST, 1);
                else
                    emg_cycles.ST{c} = nan(1001, 1);
                end
            end
            
            % Save file
            output_filename = sprintf('%s/Processed_%s_%s_trial%d.mat', output_dir, condition, controller, trial_num);
            save(output_filename, ...
                'emg_cycles', 'knee_cycles', 'condition', 'controller', 'trial_num', ...
                'pgc_emg', 'pgc_knee', 'n_cycles');
            
            fprintf('    ✓ Saved: %s\n', output_filename);
            successful = successful + 1;
            
        catch ME
            fprintf('    ✗ ERROR: %s\n', ME.message);
            failed = failed + 1;
        end
    end
    
    % Summary
    fprintf('\n');
    fprintf('%s\n', repmat('=', 1, 80));
    fprintf('BATCH PROCESSING COMPLETE\n');
    fprintf('%s\n', repmat('=', 1, 80));
    fprintf('Successful: %d / %d\n', successful, num_trials);
    fprintf('Failed: %d / %d\n', failed, num_trials);
    fprintf('Output location: %s/\n', output_dir);
    fprintf('\n');
    
    return;  % Exit after batch processing
else
    % ===== SINGLE TRIAL PROCESSING =====
    % Create display list for dialog
    trial_display = {};
    for i = 1:size(available_trials, 1)
        cond = available_trials{i, 1};
        ctrl = available_trials{i, 2};
        tn = available_trials{i, 3};
        trial_display{i} = sprintf('%s - %s - Trial %d', cond, ctrl, tn);
    end
    
    % UI Dialog for trial selection
    [trial_idx, ok] = listdlg(...
        'ListString', trial_display, ...
        'SelectionMode', 'single', ...
        'Name', 'Select Trial to Process', ...
        'PromptString', 'Choose a trial:', ...
        'ListSize', [400 300]);
    
    if ~ok || isempty(trial_idx)
        error('No trial selected. Exiting.');
    end
    
    % Extract selected trial info
    condition = available_trials{trial_idx, 1};
    controller = available_trials{trial_idx, 2};
    trial_num = available_trials{trial_idx, 3};
    
    fprintf('\n===== SELECTED TRIAL =====\n');
    fprintf('Condition: %s\n', condition);
    fprintf('Controller: %s\n', controller);
    fprintf('Trial: %d\n', trial_num);
end

% (No MVC here — envelopes are saved raw; normalization is applied downstream.)
% =========================================================================
%  1. READ HDF5 FILE
% =========================================================================

% Build HDF5 path from selected trial
h5_path = sprintf('/conditions/%s/%s/trial_%d/data', condition, controller, trial_num);
fprintf('Reading: %s\n', h5_path);

% Read scalar columns (1D arrays)
Time = h5read(h5_file, [h5_path '/Time']);
HS_Flag = h5read(h5_file, [h5_path '/HS_Flag']);
Knee_Angle = h5read(h5_file, [h5_path '/Knee_Angle']);

% Read EMG columns (2D arrays: n_rows × 100_samples)
EMG_VL_2d = h5read(h5_file, [h5_path '/EMG_VL']);
EMG_RF_2d = h5read(h5_file, [h5_path '/EMG_RF']);
EMG_BF_2d = h5read(h5_file, [h5_path '/EMG_BF']);
EMG_ST_2d = h5read(h5_file, [h5_path '/EMG_ST']);

fprintf('Loaded %d rows with 100 EMG samples per row.\n', length(Time));
fprintf('HS_Flag unique values: ');
disp(unique(HS_Flag)');

% Create table with EMG as cell arrays (each row has 100 samples)
% Convert 2D arrays to cell arrays: each column becomes a cell with 100 samples
n_rows = length(Time);
EMG_VL_cells = cell(n_rows, 1);
EMG_RF_cells = cell(n_rows, 1);
EMG_BF_cells = cell(n_rows, 1);
EMG_ST_cells = cell(n_rows, 1);

for i = 1:n_rows
    EMG_VL_cells{i} = EMG_VL_2d(:, i);
    EMG_RF_cells{i} = EMG_RF_2d(:, i);
    EMG_BF_cells{i} = EMG_BF_2d(:, i);
    EMG_ST_cells{i} = EMG_ST_2d(:, i);
end

% Create table with cell array columns
T = table(Time, HS_Flag, Knee_Angle, EMG_VL_cells, EMG_RF_cells, EMG_BF_cells, EMG_ST_cells);
T.Properties.VariableNames = {'Time', 'HS_Flag', 'Knee_Angle', 'EMG_VL', 'EMG_RF', 'EMG_BF', 'EMG_ST'};


%% 

% =========================================================================
%  2. FIND HEEL STRIKE INDICES
% =========================================================================
% Robust HS_Flag access: try named column first, fall back to column index 2
% (guards against readtable renaming the column on malformed headers)
if any(strcmp(T.Properties.VariableNames, 'HS_Flag'))
    hs_vec = T.HS_Flag;
else
    warning('HS_Flag column name not found — reading by position (col 2).');
    hs_vec = table2array(T(:, 2));
end
hs_indices = find(hs_vec == 1);
n_cycles   = length(hs_indices) - 1;  % N gait cycles between consecutive HS

if n_cycles < 1
    error('Not enough heel strikes found in the data.');
end
fprintf('Found %d complete gait cycles.\n', n_cycles);

% =========================================================================
%  3. HELPER FUNCTION: Get EMG data for rows
% =========================================================================
get_emg = @(T, rows, muscle) get_emg_from_cells(T, rows, muscle);

% =========================================================================
%  4. PROCESS EACH GAIT CYCLE
% =========================================================================
pgc_knee = linspace(0, 100, 100)';   % 100-point axis for knee angle
pgc_emg  = linspace(0, 100, 1001)';  % 1001-point axis for EMG

knee_cycles = cell(n_cycles, 1);
emg_cycles.VL = cell(n_cycles, 1);
emg_cycles.RF = cell(n_cycles, 1);
emg_cycles.BF = cell(n_cycles, 1);
emg_cycles.ST = cell(n_cycles, 1);

for c = 1 : n_cycles
    idx_start = hs_indices(c);
    idx_end   = hs_indices(c + 1) - 1;

    rows = idx_start : idx_end;

    % ------------------------------------------------------------------
    %  4a. KNEE ANGLE — normalize to 100 points (0-100% gait cycle)
    % ------------------------------------------------------------------
    knee_raw = T.Knee_Angle(rows);
    knee_raw = knee_raw(~isnan(knee_raw));

    if length(knee_raw) >= 2
        x_knee     = linspace(0, 100, length(knee_raw));
        knee_norm  = interp1(x_knee, knee_raw, pgc_knee, 'spline');
    else
        knee_norm = nan(100, 1);
    end
    knee_cycles{c} = knee_norm;

    % ------------------------------------------------------------------
    %  4b. EMG — concatenate all 100-sample packets in this gait cycle
    % ------------------------------------------------------------------
    raw_VL = get_emg(T, rows, 'VL');
    raw_RF = get_emg(T, rows, 'RF');
    raw_BF = get_emg(T, rows, 'BF');
    raw_ST = get_emg(T, rows, 'ST');

    % Remove duplicate packets
    raw_VL = remove_duplicate_packets(raw_VL, 100);
    raw_RF = remove_duplicate_packets(raw_RF, 100);
    raw_BF = remove_duplicate_packets(raw_BF, 100);
    raw_ST = remove_duplicate_packets(raw_ST, 100);

    % ------------------------------------------------------------------
    %  4c. EMG PROCESSING — envelope (NO MVC normalization for saving)
    %      Call with mvc_value=1 to get raw envelope, normalize for plotting later
    % ------------------------------------------------------------------
    if length(raw_VL) >= 10
        [emg_cycles.VL{c}, ~] = emg_processing(raw_VL, 1);  % mvc=1 → no normalization
    else
        emg_cycles.VL{c} = nan(1001, 1);
    end
    if length(raw_RF) >= 10
        [emg_cycles.RF{c}, ~] = emg_processing(raw_RF, 1);
    else
        emg_cycles.RF{c} = nan(1001, 1);
    end
    if length(raw_BF) >= 10
        [emg_cycles.BF{c}, ~] = emg_processing(raw_BF, 1);
    else
        emg_cycles.BF{c} = nan(1001, 1);
    end
    if length(raw_ST) >= 10
        [emg_cycles.ST{c}, ~] = emg_processing(raw_ST, 1);
    else
        emg_cycles.ST{c} = nan(1001, 1);
    end

    if mod(c, 10) == 0
        fprintf('  Processed cycle %d / %d\n', c, n_cycles);
    end
end

fprintf('Processing complete.\n');

% =========================================================================
%  5. SAVE PROCESSED EMG DATA (UN-NORMALIZED) TO .mat FILE
% =========================================================================

% Save raw processed EMG (no MVC normalization) for flexible comparisons
output_filename = sprintf('%s/Processed_%s_%s_trial%d.mat', output_dir, condition, controller, trial_num);
fprintf('\nSaving processed EMG data to: %s\n', output_filename);

% Store EMG data at 1001-point resampled scale (matching gait cycle)
save(output_filename, ...
    'emg_cycles', ...
    'knee_cycles', ...
    'condition', 'controller', 'trial_num', ...
    'pgc_emg', 'pgc_knee', ...
    'n_cycles');

fprintf('✓ Saved: %s\n', output_filename);
fprintf('  Contains: emg_cycles (VL, RF, BF, ST at 1001 points)\n');
fprintf('  Contains: knee_cycles (100 points)\n');
fprintf('  Contains: trial metadata (condition, controller, trial_num)\n');

% =========================================================================
%  6. VISUALIZE WITH MVC NORMALIZATION (FOR PLOTTING ONLY)
% =========================================================================
knee_mat = cell2mat(knee_cycles');        % 100 x N_cycles

% Raw EMG envelopes (not MVC-normalized, as saved)
VL_mat_raw = cell2mat(emg_cycles.VL');   % 1001 x N_cycles
RF_mat_raw = cell2mat(emg_cycles.RF');
BF_mat_raw = cell2mat(emg_cycles.BF');
ST_mat_raw = cell2mat(emg_cycles.ST');

% Plot raw EMG envelopes (no MVC normalization — done downstream)
VL_mat = VL_mat_raw;
RF_mat = RF_mat_raw;
BF_mat = BF_mat_raw;
ST_mat = ST_mat_raw;
%% 

% =========================================================================
%  7. PLOT RESULTS (normalized for visualization)
% =========================================================================
figure('Name', 'Gait Cycle Analysis', 'Color', 'w', 'Position', [100 100 1400 700]);

% Knee Angle
subplot(2, 3, 1);
plot_mean_sd(pgc_knee, knee_mat, 'Knee Angle (°)', [0 100], 'b');
title('Knee Angle');

muscles = {'VL', 'RF', 'BF', 'ST'};
mats    = {VL_mat, RF_mat, BF_mat, ST_mat};
colors  = {[0.85 0.33 0.10], [0.47 0.67 0.19], [0.30 0.75 0.93], [0.64 0.08 0.18]};

for m = 1 : 4
    subplot(2, 3, m + 1);
    plot_mean_sd(pgc_emg, mats{m}, 'EMG env (a.u.)', [0 100], colors{m});
    title(muscles{m});
end

sgtitle('Gait Cycle Kinematics & Muscle Activity (Mean ± SD)');

% =========================================================================
%  LOCAL FUNCTIONS
% =========================================================================
function plot_mean_sd(pgc, data_mat, ylabel_str, xlim_val, col)
    valid      = ~all(isnan(data_mat), 1);
    data_valid = data_mat(:, valid);
    mn  = mean(data_valid, 2, 'omitnan');
    sd  = std(data_valid, 0, 2, 'omitnan');
    fill([pgc; flipud(pgc)], [mn - sd; flipud(mn + sd)], col, ...
        'FaceAlpha', 0.2, 'EdgeColor', 'none');
    hold on;
    plot(pgc, mn, 'Color', col, 'LineWidth', 2);
    xlabel('Gait Cycle (%)');
    ylabel(ylabel_str);
    xlim(xlim_val);
    grid on; box off;
end

function out = remove_duplicate_packets(data, pkt_size)
    if isempty(data) || length(data) < pkt_size
        out = data; return;
    end
    n_pkts = floor(length(data) / pkt_size);
    pkts   = reshape(data(1 : n_pkts * pkt_size), pkt_size, n_pkts);
    keep   = true(1, n_pkts);
    for i = 2 : n_pkts
        if isequal(pkts(:, i), pkts(:, i-1)), keep(i) = false; end
    end
    out = pkts(:, keep); out = out(:);
end

% Get EMG data from HDF5-based table (cell array format)
% Concatenate all 100-sample packets into raw EMG vector for emg_processing
function out = get_emg_from_cells(T, rows, muscle)
    col_name = ['EMG_' muscle];
    emg_cells = T.(col_name)(rows);  % Get cell array for these rows
    
    % Concatenate all 100-sample packets from this cycle
    % emg_processing needs raw samples to compute bandpass + rolling RMS envelope
    data = [];
    for i = 1:length(emg_cells)
        cell_data = emg_cells{i};
        if ~isempty(cell_data) && ~all(isnan(cell_data))
            data = [data; cell_data(:)];  % Concatenate vertically
        end
    end
    out = data;
end
