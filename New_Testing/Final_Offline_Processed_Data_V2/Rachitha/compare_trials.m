%% compare_trials.m
% Compare muscle activity across 3 processed gait cycle trials
%
% Features:
%   - Load 3 processed trial .mat files
%   - Apply MVC normalization to each trial's EMG
%   - Compare muscle activity (VL, RF, BF, ST) across trials
%   - Visualize mean envelopes side-by-side
%   - Generate comparison statistics
%
% USAGE:
%   1. Run script
%   2. Select 3 .mat files (e.g., Processed_inc0_spd0p8_active_rl_trial1.mat)
%   3. Envelopes loaded (already resampled to 1001 points)
%   4. MVC normalization applied
%   5. Comparison plots generated

clear all; close all; clc;
N_Trials = 3;

% >>> FIGURE LABELS <<< true = annotate all figures (axis labels, titles,
% legends, x-tick condition names); false = bare figures for the paper.
show_labels = true;
fprintf('="*80\n');
fprintf('TRIAL COMPARISON TOOL - Load Trials\n');
fprintf('="*80\n\n');

%% ===== MVC VALUES FOR EACH TRIAL =====
% Define trial-specific MVC values here
% Format: mvc_trial{trial_number}.mvc_VL, .mvc_RF, .mvc_BF, .mvc_ST
% If empty, will load from .mat file metadata

% Trial 1 MVC values (set to [] to load from .mat file)


mvc_trial{1}.mvc_VL = 0.000027506719480932594;
mvc_trial{1}.mvc_RF = 0.0001471910522412176; 
mvc_trial{1}.mvc_BF = 0.00003703623363533903;
mvc_trial{1}.mvc_ST = 1.575077217024475e-05;

% Trial 2 MVC values (set to [] to load from .mat file)

mvc_trial{2}.mvc_VL = 0.000027506719480932594;
mvc_trial{2}.mvc_RF = 0.0001471910522412176; 
mvc_trial{2}.mvc_BF = 0.00003703623363533903;
mvc_trial{2}.mvc_ST = 1.575077217024475e-05;

% Trial 3 MVC values (set to [] to load from .mat file)

mvc_trial{3}.mvc_VL = 0.000027506719480932594;
mvc_trial{3}.mvc_RF = 0.0001471910522412176; 
mvc_trial{3}.mvc_BF = 0.00003703623363533903;
mvc_trial{3}.mvc_ST = 1.575077217024475e-05;



%% ===== STEP 1: SELECT 3 PROCESSED TRIAL MAT FILES =====

trial_files = cell(N_Trials, 1);
trial_names = {};
mvc_values = {};

for t = 1:N_Trials
    fprintf('\nSelect Trial %d:\n', t);
    [filename, filepath] = uigetfile('*.mat', ...
        sprintf('Select processed trial file #%d', t), ...
        './');
    
    if ~filename
        error('Trial %d not selected. Exiting.', t);
    end
    
    full_path = fullfile(filepath, filename);
    trial_files{t} = full_path;
    
    % Extract trial info from filename
    % Format: Processed_{condition}_{controller}_trial{num}.mat
    name_parts = strsplit(filename(1:end-4), '_');  % Remove .mat and split
    
    % Reconstruct condition and controller from parts
    % Typically: Processed_inc0_spd0p8_active_rl_trial1
    if contains(filename, 'inc')
        % Find 'inc' position
        inc_pos = find(filename == 'i', 1);
        condition_part = filename(inc_pos:inc_pos+7);  % e.g., inc0_spd0
        if contains(filename(inc_pos:end), 'inc5')
            condition_part = filename(inc_pos:inc_pos+8);  % inc5_spd0
        end
        
        % Extract controller (between speed and 'trial')
        controller_part = extractBetween(filename, 'spd\w+_', '_trial');
        if isempty(controller_part)
            controller_part = extractBetween(filename, 'spd\w+_', '_trial\d');
        end
        
        % Simpler approach: manually extract from parts
        if length(name_parts) >= 4
            % Try to reconstruct from parts
            cond = sprintf('%s_%s', name_parts{2}, name_parts{3});
            ctrl = name_parts{4};
        else
            cond = 'unknown_condition';
            ctrl = 'unknown_controller';
        end
    else
        cond = 'unknown';
        ctrl = 'unknown';
    end
    
    fprintf('  File: %s\n', filename);
    fprintf('  Condition: %s, Controller: %s\n', cond, ctrl);
    trial_names{t} = sprintf('%s-%s', cond, ctrl);
    
    % Load to extract MVC values (if not already defined above)
    temp_data = load(full_path, 'mvc_VL', 'mvc_RF', 'mvc_BF', 'mvc_ST');
    
    % Use defined MVC values if they exist, otherwise use loaded ones
    if isfield(mvc_trial{t}, 'mvc_VL') && ~isempty(mvc_trial{t}.mvc_VL)
        mvc_values{t} = mvc_trial{t};  % Use predefined values
        fprintf('  Using predefined MVC values for Trial %d\n', t);
    else
        mvc_values{t} = temp_data;  % Load from .mat file
        fprintf('  Using MVC values from .mat file for Trial %d\n', t);
    end
end

%% ===== STEP 2: LOAD PROCESSED EMG CYCLES =====

fprintf('\n\nLoading trial data...\n');

trial_data = {};
for t = 1:N_Trials
    data = load(trial_files{t}, 'emg_cycles', 'knee_cycles', 'pgc_emg', 'pgc_knee', 'n_cycles');
    trial_data{t} = data;
    
    fprintf('  Trial %d: %d gait cycles loaded\n', t, data.n_cycles);
end

%% ===== STEP 3: COMPUTE ENVELOPES + PER-STRIDE SCALARS (MVC NORMALIZED) =====
% Statistical structure (applied everywhere below):
%   1) normalize each stride to % MVC
%   2) collapse each STRIDE to a scalar first (whole-cycle mean, peak, iEMG)
%   3) THEN take mean +/- SD ACROSS STRIDES
% This makes every reported SD a stride-to-stride variability, NOT the
% within-cycle waveform shape (which is what inflates a pooled-points SD).

fprintf('\n\nComputing envelopes + per-stride scalars with MVC normalization...\n');

pgc = trial_data{1}.pgc_emg;          % gait-cycle axis (0-100%), shared
mnames = {'VL', 'RF', 'BF', 'ST'};

means = struct();
trial_norm = cell(N_Trials, 1);       % store normalized matrices for reuse

for t = 1:N_Trials
    mvc = mvc_values{t};

    % Normalize each muscle to % MVC:  1001 x N_cycles
    nrm = struct();
    nrm.VL = cell2mat(trial_data{t}.emg_cycles.VL') ./ mvc.mvc_VL * 100;
    nrm.RF = cell2mat(trial_data{t}.emg_cycles.RF') ./ mvc.mvc_RF * 100;
    nrm.BF = cell2mat(trial_data{t}.emg_cycles.BF') ./ mvc.mvc_BF * 100;
    nrm.ST = cell2mat(trial_data{t}.emg_cycles.ST') ./ mvc.mvc_ST * 100;
    trial_norm{t} = nrm;

    for k = 1:4
        M = mnames{k};
        X = nrm.(M);                                  % 1001 x N_cycles

        % --- Full waveform: mean +/- SD across strides at each % GC point ---
        means(t).(M)          = mean(X, 2, 'omitnan');
        means(t).([M '_sd'])  = std(X, 0, 2, 'omitnan');

        % --- Per-stride scalars (one number per stride) ---
        cyc_strides  = mean(X, 1, 'omitnan');         % whole-cycle mean / stride
        peak_strides = max(X, [], 1, 'omitnan');      % peak activation  / stride
        iemg_strides = trapz(pgc, X, 1);              % iEMG (area)      / stride

        % --- Mean +/- SD ACROSS strides ---
        means(t).(['mean_' M])   = mean(cyc_strides,  'omitnan');
        means(t).(['std_'  M])   = std(cyc_strides, 0, 'omitnan');
        means(t).(['peak_' M])   = mean(peak_strides, 'omitnan');
        means(t).(['peaksd_' M]) = std(peak_strides, 0, 'omitnan');
        means(t).(['iemg_' M])   = mean(iemg_strides, 'omitnan');
        means(t).(['iemgsd_' M]) = std(iemg_strides, 0, 'omitnan');
    end

    fprintf('  Trial %d: VL cyc-mean=%.1f%% MVC, RF cyc-mean=%.1f%% MVC\n', ...
        t, means(t).mean_VL, means(t).mean_RF);
end

%% ===== STEP 4: COMPARISON PLOTS (SIDE-BY-SIDE MUSCLES) =====

figure('Name', 'Trial Comparison', 'Color', 'w', 'Position', [100 100 1600 700]);

pgc = trial_data{1}.pgc_emg;  % Use first trial's gait cycle axis
colors = {[0.85 0.33 0.10], [0.47 0.67 0.19], [0.30 0.75 0.93]};  % Three distinct colors

muscles = {'VL', 'RF', 'BF', 'ST'};
raw_labels ={"","No Exosuit","","Exosuit Inactive","","Exosuit Active"};
for m = 1:4
    subplot(1, 4, m);
    hold on;
    
    for t = 1:N_Trials
        muscle_data = means(t).(muscles{m});
        muscle_sd = means(t).(sprintf('%s_sd', muscles{m}));
        
        % Plot mean with filled SD band
        fill([pgc; flipud(pgc)], ...
             [muscle_data - muscle_sd; flipud(muscle_data + muscle_sd)], ...
             colors{t}, 'FaceAlpha', 0.15, 'EdgeColor', 'none');
        
        % Plot mean line
        plot(pgc, muscle_data, 'Color', colors{t}, 'LineWidth', 5);
    end

    if show_labels
        xlabel('Gait Cycle (%)');
        ylabel('% MVC');
        title(muscles{m}, 'FontSize', 12, 'FontWeight', 'bold');
        legend(raw_labels, 'Location', 'best');
    end
    xlim([0 100]);
    ylim([0 inf]);
    fontsize(gcf, 24, "points")
    grid on; box off;
end

if show_labels
    sgtitle(sprintf('Muscle Activity Comparison - 3 Trials (%% MVC): %s vs %s vs %s', ...
        trial_names{1}, trial_names{2}, trial_names{3}));
end

%% ===== STEP 5: GENERATE COMPARISON STATISTICS =====

fprintf('\n\n');
fprintf('="*80\n');
fprintf('COMPARISON STATISTICS (Peak % MVC)\n');
fprintf('="*80\n\n');

for m = 1:4
    fprintf('%s:\n', muscles{m});
    for t = 1:N_Trials
        muscle_data = means(t).(muscles{m});
        peak = nanmax(muscle_data);
        fprintf('  Trial %d (%s):  %.1f%% MVC\n', t, trial_names{t}, peak);
    end
    fprintf('\n');
end

%% ===== STEP 6: MEAN EMG REDUCTION AND GROUPED BAR PLOT =====

muscle_means = [
    means(1).mean_VL, means(2).mean_VL, means(3).mean_VL; 
    means(1).mean_RF, means(2).mean_RF, means(3).mean_RF; 
    means(1).mean_BF, means(2).mean_BF, means(3).mean_BF; 
    means(1).mean_ST, means(2).mean_ST, means(3).mean_ST];

muscle_sds = [
    means(1).std_VL, means(2).std_VL, means(3).std_VL; 
    means(1).std_RF, means(2).std_RF, means(3).std_RF; 
    means(1).std_BF, means(2).std_BF, means(3).std_BF; 
    means(1).std_ST, means(2).std_ST, means(3).std_ST];

condition_labels = trial_names;
condition_keys = lower(strrep(strrep(strrep(condition_labels, '-', '_'), ' ', '_'), '.', '_'));
% Robust detection. NOTE: 'inactive' CONTAINS 'active', so exoactive must
% explicitly exclude the inactive trial or it can grab the wrong one.
is_noexo  = contains(condition_keys, 'noexo') | contains(condition_keys, 'no_exo');
is_inact  = contains(condition_keys, 'inactive');
is_active = contains(condition_keys, 'active') & ~is_inact;
noexo_idx       = find(is_noexo,  1);
exoinactive_idx = find(is_inact,  1);
exoactive_idx   = find(is_active, 1);

if ~isempty(noexo_idx) && ~isempty(exoactive_idx)
    reduction_pct = (muscle_means(:, noexo_idx) - muscle_means(:, exoactive_idx)) ./ muscle_means(:, noexo_idx) * 100;
    fprintf('="*80\n');
    fprintf('MEAN EMG REDUCTION FROM NOEXO TO EXOACTIVE\n');
    fprintf('="*80\n\n');
    for m = 1:4
        fprintf('%s: %.1f%% reduction\n', muscles{m}, reduction_pct(m));
    end
    fprintf('\n');
else
    warning('Could not identify both noexo and exoactive conditions from trial labels. Mean EMG reduction not computed.');
end

% ---- WHOLE-CYCLE SCALAR SUMMARY (per-stride metric, SD across strides) ----
% Three complementary whole-cycle metrics, each collapsed per stride first:
%   row 1: whole-cycle MEAN (% MVC)  -> overall activation level
%   row 2: PEAK (% MVC)              -> burst amplitude
%   row 3: iEMG (% MVC * % GC)       -> total activation / effort
bar_colors = [0.85 0.33 0.10; 0.47 0.67 0.19; 0.30 0.75 0.93];
metric_prefix = {'mean', 'peak', 'iemg'};
metric_sd     = {'std',  'peaksd', 'iemgsd'};
metric_row    = {'Whole-cycle MEAN (% MVC)', 'PEAK (% MVC)', 'iEMG (%MVC*%GC)'};

figure('Name', 'Whole-Cycle Scalar Summary', 'Color', 'w', 'Position', [200 120 1500 900]);
for r = 1:3
    for m = 1:4
        subplot(3, 4, (r-1)*4 + m); hold on;
        vals = arrayfun(@(t) means(t).(sprintf('%s_%s', metric_prefix{r}, mnames{m})), 1:N_Trials);
        errs = arrayfun(@(t) means(t).(sprintf('%s_%s', metric_sd{r},     mnames{m})), 1:N_Trials);
        b = bar(1:N_Trials, vals, 'FaceColor', 'flat'); b.CData = bar_colors;
        errorbar(1:N_Trials, vals, errs, 'k', 'linestyle', 'none', 'LineWidth', 1.5, 'CapSize', 8);
        set(gca, 'XTick', 1:N_Trials);
        if show_labels && r == 3
            set(gca, 'XTickLabel', trial_names, 'XTickLabelRotation', 20);
        else
            set(gca, 'XTickLabel', []);
        end
        if show_labels && r == 1, title(mnames{m}, 'FontWeight', 'bold'); end
        if show_labels && m == 1, ylabel(metric_row{r}); end
        xlim([0.5 N_Trials+0.5]); grid on; box off;
    end
end
if show_labels
    sgtitle('Whole-Cycle Muscle Activity (per-stride metric, SD = stride-to-stride)', ...
        'FontSize', 15, 'FontWeight', 'bold');
end

%% ===== STEP 7: ACTIVATION PATTERN SUMMARY =====

fprintf('="*80\n');
fprintf('ACTIVATION TIMING (% gait cycle at peak activity)\n');
fprintf('="*80\n\n');

for m = 1:4
    fprintf('%s:\n', muscles{m});
    for t = 1:N_Trials
        muscle_data = means(t).(muscles{m});
        [~, peak_idx] = nanmax(muscle_data);
        peak_time = pgc(peak_idx);
        fprintf('  Trial %d (%s):  %.0f%% GC\n', t, trial_names{t}, peak_time);
    end
    fprintf('\n');
end

fprintf('="*80\n');
fprintf('Comparison complete. Figure saved for visualization.\n');
%% ===== STEP 8: FULLY-CROSSED FUNCTIONAL ZONE ANALYSIS (ALL MUSCLES x BOTH ZONES) =====
% Rationale: restricting each muscle to its "primary" zone hides the exosuit's
% effect on the ANTAGONISTS. The suit applies an EXTENSION torque, so its most
% telling off-target effect is on the FLEXORS during the EXTENSION phases.
% Here every muscle is measured in BOTH zones (per-stride mean, SD across strides),
% so those off-target effects are visible instead of averaged away.
fprintf('\n\n');
fprintf('="*80\n');
fprintf('FULLY-CROSSED ZONE ANALYSIS: ALL MUSCLES x BOTH ZONES\n');
fprintf('="*80\n\n');

% 1. Define Combined Gait Cycle Indices based on the pgc array (0-100%)
% Extension phases: 13-37% OR 68-100%
idx_ext_combined = (pgc >= 13 & pgc < 37) | (pgc >= 68 & pgc <= 100);
% Flexion phases:   0-13% OR 37-68%
idx_flex_combined = (pgc >= 0 & pgc < 13) | (pgc >= 37 & pgc < 68);

zone_idx  = {idx_ext_combined, idx_flex_combined};
zone_key  = {'ext', 'flex'};

% Per-stride mean within each zone, THEN mean & SD across strides
z_metrics = struct();
for t = 1:N_Trials
    for k = 1:4
        M = mnames{k};
        X = trial_norm{t}.(M);
        for z = 1:2
            per_stride = mean(X(zone_idx{z}, :), 1, 'omitnan');   % 1 x N_cycles
            z_metrics(t).(sprintf('%s_%s_mean', M, zone_key{z})) = mean(per_stride, 'omitnan');
            z_metrics(t).(sprintf('%s_%s_sd',   M, zone_key{z})) = std(per_stride, 0, 'omitnan');
        end
    end
end

% 2. Reductions (No Exo -> Exo Active) for EVERY muscle in BOTH zones
if ~isempty(noexo_idx) && ~isempty(exoactive_idx)
    calc_red = @(f) ((z_metrics(noexo_idx).(f) - z_metrics(exoactive_idx).(f)) / z_metrics(noexo_idx).(f)) * 100;
    fprintf('--- REDUCTIONS (No Exo -> Exo Active), +ve = decrease ---\n');
    fprintf('%-4s | %14s | %14s\n', 'Musc', 'Extension zone', 'Flexion zone');
    for k = 1:4
        M = mnames{k};
        fprintf('%-4s | %12.2f%% | %12.2f%%\n', M, ...
            calc_red(sprintf('%s_ext_mean', M)), calc_red(sprintf('%s_flex_mean', M)));
    end
    fprintf(['\nNote: flexor (BF/ST) rows in the EXTENSION-zone column are the ' ...
             'off-target\n      effect of the suit''s extension support that the ' ...
             'old scheme hid.\n\n']);
end

% 3. Plot: 2 rows (zones) x 4 cols (muscles). Row1 = extension zone, Row2 = flexion zone.
bar_colors = [0.85 0.33 0.10; 0.47 0.67 0.19; 0.30 0.75 0.93];
zone_row_label = {'Extension zone (% MVC)', 'Flexion zone (% MVC)'};

figure('Name', 'Fully-Crossed Functional Zone Analysis', 'Color', 'w', 'Position', [150 120 1500 900]);
for z = 1:2
    for m = 1:4
        subplot(2, 4, (z-1)*4 + m); hold on;
        vals = arrayfun(@(t) z_metrics(t).(sprintf('%s_%s_mean', mnames{m}, zone_key{z})), 1:N_Trials);
        errs = arrayfun(@(t) z_metrics(t).(sprintf('%s_%s_sd',   mnames{m}, zone_key{z})), 1:N_Trials);
        b = bar(1:N_Trials, vals, 'FaceColor', 'flat'); b.CData = bar_colors;
        errorbar(1:N_Trials, vals, errs, 'k', 'linestyle', 'none', 'LineWidth', 1.5, 'CapSize', 8);
        set(gca, 'XTick', 1:N_Trials);
        if show_labels && z == 2
            set(gca, 'XTickLabel', trial_names, 'XTickLabelRotation', 20);
        else
            set(gca, 'XTickLabel', []);
        end
        if show_labels && z == 1, title(mnames{m}, 'FontWeight', 'bold'); end
        if show_labels && m == 1, ylabel(zone_row_label{z}); end
        xlim([0.5 N_Trials+0.5]); grid on; box off;
    end
end
if show_labels
    sgtitle('Muscle Activity in BOTH Functional Zones (per-stride, SD = stride-to-stride)', ...
        'FontSize', 15, 'FontWeight', 'bold');
end

% %% ===== STEP 9: COMBINED FUNCTIONAL ZONE ANALYSIS (INTEGRAL / iEMG) =====
% fprintf('\n\n');
% fprintf('="*80\n');
% fprintf('COMBINED ZONE ANALYSIS: INTEGRALS (iEMG) & REDUCTIONS\n');
% fprintf('="*80\n\n');
% 
% % Initialize struct to hold zone metrics across trials for integral
% i_metrics = struct();
% 
% for t = 1:N_Trials
%     % Recreate normalized matrices to calculate stride-to-stride variance
%     VL_norm = cell2mat(trial_data{t}.emg_cycles.VL') ./ mvc_values{t}.mvc_VL * 100;
%     RF_norm = cell2mat(trial_data{t}.emg_cycles.RF') ./ mvc_values{t}.mvc_RF * 100;
%     BF_norm = cell2mat(trial_data{t}.emg_cycles.BF') ./ mvc_values{t}.mvc_BF * 100;
%     ST_norm = cell2mat(trial_data{t}.emg_cycles.ST') ./ mvc_values{t}.mvc_ST * 100;
% 
%     % --- EXTENSORS (VL & RF) in Combined Extension Phase ---
%     % Calculate the integral (area under curve) within the combined zone FOR EACH STRIDE, then take overall mean & std
% 
%     % Note: pgc(idx) is a column vector, emg_norm(idx, :) are the columns. 
%     % We integrate along dimension 1 (time/pgc).
%     VL_int_strides = trapz(pgc(idx_ext_combined), VL_norm(idx_ext_combined, :), 1);
%     i_metrics(t).VL_ext_int_mean = mean(VL_int_strides, 'omitnan');
%     i_metrics(t).VL_ext_int_sd   = std(VL_int_strides, 0, 'omitnan');
% 
%     RF_int_strides = trapz(pgc(idx_ext_combined), RF_norm(idx_ext_combined, :), 1);
%     i_metrics(t).RF_ext_int_mean = mean(RF_int_strides, 'omitnan');
%     i_metrics(t).RF_ext_int_sd   = std(RF_int_strides, 0, 'omitnan');
% 
%     % --- FLEXORS (BF & ST) in Combined Flexion Phase ---
%     BF_int_strides = trapz(pgc(idx_flex_combined), BF_norm(idx_flex_combined, :), 1);
%     i_metrics(t).BF_flex_int_mean = mean(BF_int_strides, 'omitnan');
%     i_metrics(t).BF_flex_int_sd   = std(BF_int_strides, 0, 'omitnan');
% 
%     ST_int_strides = trapz(pgc(idx_flex_combined), ST_norm(idx_flex_combined, :), 1);
%     i_metrics(t).ST_flex_int_mean = mean(ST_int_strides, 'omitnan');
%     i_metrics(t).ST_flex_int_sd   = std(ST_int_strides, 0, 'omitnan');
% end
% 
% % 2. Calculate Reductions (No Exo vs Exo Active)
% if ~isempty(noexo_idx) && ~isempty(exoactive_idx)
%     % Helper function for percentage reduction
%     calc_red_int = @(m_name) ((i_metrics(noexo_idx).(m_name) - i_metrics(exoactive_idx).(m_name)) / i_metrics(noexo_idx).(m_name)) * 100;
% 
%     fprintf('--- OVERALL REDUCTIONS (No Exo -> Exo Active) using INTEGRAL ---\n');
%     fprintf('VL | Total Extension Phase: %6.2f%% reduction\n', calc_red_int('VL_ext_int_mean'));
%     fprintf('RF | Total Extension Phase: %6.2f%% reduction\n', calc_red_int('RF_ext_int_mean'));
%     fprintf('BF | Total Flexion Phase:   %6.2f%% reduction\n', calc_red_int('BF_flex_int_mean'));
%     fprintf('ST | Total Flexion Phase:   %6.2f%% reduction\n\n', calc_red_int('ST_flex_int_mean'));
% end
% 
% % 3. Plotting Setup: A single 2x2 grid for all 4 muscles
% figure('Name', 'Combined Functional Zone Analysis (Integral/iEMG)', 'Color', 'w', 'Position', [200 200 1200 800]);
% 
% % Setup Plotting Arrays
% plot_fields_int = {'VL_ext_int', 'RF_ext_int', 'BF_flex_int', 'ST_flex_int'};
% plot_titles_int = {'Vastus Lateralis (VL) iEMG During Extension', ...
%                'Rectus Femoris (RF) iEMG During Extension', ...
%                'Biceps Femoris (BF) iEMG During Flexion', ...
%                'Semitendinosus (ST) iEMG During Flexion'};
% 
% for i = 1:4
%     subplot(2, 2, i); hold on;
%     means_to_plot_int = [i_metrics(1).(sprintf('%s_mean', plot_fields_int{i})), ...
%                          i_metrics(2).(sprintf('%s_mean', plot_fields_int{i})), ...
%                          i_metrics(3).(sprintf('%s_mean', plot_fields_int{i}))];
%     sds_to_plot_int   = [i_metrics(1).(sprintf('%s_sd', plot_fields_int{i})), ...
%                          i_metrics(2).(sprintf('%s_sd', plot_fields_int{i})), ...
%                          i_metrics(3).(sprintf('%s_sd', plot_fields_int{i}))];
% 
%     b_int = bar(x_labels, means_to_plot_int, 'FaceColor', 'flat');
%     b_int.CData = bar_colors;
% 
%     % Add error bars
%     errorbar(1:3, means_to_plot_int, sds_to_plot_int, 'k', 'linestyle', 'none', 'LineWidth', 1.5, 'CapSize', 8);
% 
%     ylabel('Integrated EMG (% MVC * % GC)', 'FontWeight', 'bold');
%     title(plot_titles_int{i}, 'FontSize', 12);
% 
%     % Add y-axis breathing room for the error bars
%     max_val_int = max(means_to_plot_int + sds_to_plot_int);
%     ylim([0, max_val_int * 1.2]);
% 
%     grid on; box off;
% end
% sgtitle('Targeted Muscle Activity (iEMG) During Primary Functional Phases', 'FontSize', 15, 'FontWeight', 'bold');

%% ===== STEP 9: PACKAGE METRICS FOR SAVING (one workspace var per speed x incline) =====
% Bundles every useful scalar for THIS comparison (noexo / exoinactive /
% exoactive at one speed & incline) into a single struct `metrics`, in a fixed
% canonical condition order so downstream aggregation is consistent.
% After running, save it manually, e.g.:
%   save(sprintf('%s_metrics.mat', metrics.tag), 'metrics');

cond_order = [noexo_idx, exoinactive_idx, exoactive_idx];
cond_names = {'noexo', 'exoinactive', 'exoactive'};

if any(cellfun(@isempty, num2cell(cond_order))) || numel(cond_order) < 3
    warning(['Could not identify all three conditions (noexo/exoinactive/' ...
        'exoactive) from the selected files. `metrics` not built.']);
else
    % --- Metadata parsed from the first selected filename / its folder ---
    [fpath1, fname1] = fileparts(trial_files{1});
    [~, subj_name]   = fileparts(fpath1);
    inc_tok = regexp(fname1, 'inc(\d+)',        'tokens', 'once');
    spd_tok = regexp(fname1, 'spd([0-9p\.]+)',  'tokens', 'once');

    metrics = struct();
    metrics.subject    = subj_name;
    metrics.incline    = str2double(inc_tok{1});                       % 0 or 5 (deg)
    metrics.speed      = str2double(strrep(spd_tok{1}, 'p', '.'));     % m/s
    metrics.conditions = cond_names;      % row order of every matrix below
    metrics.muscles    = mnames;          % column order of every matrix below
    metrics.zones      = {'ext', 'flex'};
    metrics.tag = sprintf('%s_inc%d_spd%s', subj_name, metrics.incline, ...
        strrep(num2str(metrics.speed), '.', 'p'));

    % All metric matrices are [3 conditions x 4 muscles]; SD = across-stride.
    Z = nan(3, 4);
    metrics.n_cycles        = nan(1, 3);
    metrics.wholecycle_mean = Z; metrics.wholecycle_sd = Z;   % whole-cycle mean %MVC
    metrics.peak_mean       = Z; metrics.peak_sd       = Z;   % peak %MVC
    metrics.iemg_mean       = Z; metrics.iemg_sd       = Z;   % iEMG (%MVC*%GC)
    metrics.ext_zone_mean   = Z; metrics.ext_zone_sd   = Z;   % extension-phase mean
    metrics.flex_zone_mean  = Z; metrics.flex_zone_sd  = Z;   % flexion-phase mean

    for ci = 1:3
        t = cond_order(ci);
        metrics.n_cycles(ci) = trial_data{t}.n_cycles;
        for k = 1:4
            M = mnames{k};
            metrics.wholecycle_mean(ci, k) = means(t).(['mean_'   M]);
            metrics.wholecycle_sd(ci, k)   = means(t).(['std_'    M]);
            metrics.peak_mean(ci, k)       = means(t).(['peak_'   M]);
            metrics.peak_sd(ci, k)         = means(t).(['peaksd_' M]);
            metrics.iemg_mean(ci, k)       = means(t).(['iemg_'   M]);
            metrics.iemg_sd(ci, k)         = means(t).(['iemgsd_' M]);
            metrics.ext_zone_mean(ci, k)   = z_metrics(t).([M '_ext_mean']);
            metrics.ext_zone_sd(ci, k)     = z_metrics(t).([M '_ext_sd']);
            metrics.flex_zone_mean(ci, k)  = z_metrics(t).([M '_flex_mean']);
            metrics.flex_zone_sd(ci, k)    = z_metrics(t).([M '_flex_sd']);
        end
    end

    fprintf('\n="*80\n');
    fprintf('METRICS PACKAGED into workspace variable `metrics`\n');
    fprintf('  subject=%s  incline=%d  speed=%.2f  (order: noexo, exoinactive, exoactive)\n', ...
        metrics.subject, metrics.incline, metrics.speed);
    fprintf('  Save it with:  save(''%s_metrics.mat'', ''metrics'')\n', metrics.tag);
    fprintf('="*80\n');
end

%% ===== UTILITY FUNCTION: Split string =====

function parts = strsplit(str, delimiter)
    % Simple strsplit implementation for older MATLAB versions
    if verLessThan('matlab', '9.0')  % Before R2016a
        parts = textscan(str, '%s', 'Delimiter', delimiter);
        parts = parts{1}';
    else
        parts = split(str, delimiter);
    end
end
