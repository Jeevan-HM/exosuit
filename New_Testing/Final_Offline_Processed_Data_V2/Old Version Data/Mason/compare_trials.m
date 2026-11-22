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
fprintf('="*80\n');
fprintf('TRIAL COMPARISON TOOL - Load Trials\n');
fprintf('="*80\n\n');

%% ===== MVC VALUES FOR EACH TRIAL =====
% Define trial-specific MVC values here
% Format: mvc_trial{trial_number}.mvc_VL, .mvc_RF, .mvc_BF, .mvc_ST
% If empty, will load from .mat file metadata

% Trial 1 MVC values (set to [] to load from .mat file)


mvc_trial{1}.mvc_VL =  0.000021694004690864943*5;
mvc_trial{1}.mvc_RF = 0.00006952421681286414; 
mvc_trial{1}.mvc_BF = 6.0630176137569e-05;
mvc_trial{1}.mvc_ST = 0.0018490477291853277*0.05;

% Trial 2 MVC values (set to [] to load from .mat file)

mvc_trial{2}.mvc_VL =  0.000021694004690864943*5;
mvc_trial{2}.mvc_RF = 0.00006952421681286414; 
mvc_trial{2}.mvc_BF = 6.0630176137569e-05;
mvc_trial{2}.mvc_ST = 0.0018490477291853277*0.05;

% Trial 3 MVC values (set to [] to load from .mat file)

mvc_trial{3}.mvc_VL =  0.000021694004690864943*5;
mvc_trial{3}.mvc_RF = 0.00006952421681286414; 
mvc_trial{3}.mvc_BF = 6.0630176137569e-05;
mvc_trial{3}.mvc_ST = 0.0018490477291853277*0.05;

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

%% ===== STEP 3: COMPUTE MEAN ENVELOPES AND APPLY MVC NORMALIZATION =====

fprintf('\n\nComputing mean envelopes with MVC normalization...\n');

means = struct();

for t = 1:N_Trials
    % Convert to matrices
    VL_raw = cell2mat(trial_data{t}.emg_cycles.VL');  % 1001 x N_cycles
    RF_raw = cell2mat(trial_data{t}.emg_cycles.RF');
    BF_raw = cell2mat(trial_data{t}.emg_cycles.BF');
    ST_raw = cell2mat(trial_data{t}.emg_cycles.ST');
    
    % Get MVC values for this trial
    mvc = mvc_values{t};
    
    % Normalize to % MVC
    VL_norm = VL_raw ./ mvc.mvc_VL * 100;
    RF_norm = RF_raw ./ mvc.mvc_RF * 100;
    BF_norm = BF_raw ./ mvc.mvc_BF * 100;
    ST_norm = ST_raw ./ mvc.mvc_ST * 100;
    
    % Compute means and SDs
    means(t).VL = mean(VL_norm, 2, 'omitnan');
    means(t).VL_sd = std(VL_norm, 0, 2, 'omitnan');
    means(t).RF = mean(RF_norm, 2, 'omitnan');
    means(t).RF_sd = std(RF_norm, 0, 2, 'omitnan');
    means(t).BF = mean(BF_norm, 2, 'omitnan');
    means(t).BF_sd = std(BF_norm, 0, 2, 'omitnan');
    means(t).ST = mean(ST_norm, 2, 'omitnan');
    means(t).ST_sd = std(ST_norm, 0, 2, 'omitnan');
    
    % Overall mean and SD across all normalized EMG points for bar plot summaries
    all_VL = VL_norm(:);
    all_RF = RF_norm(:);
    all_BF = BF_norm(:);
    all_ST = ST_norm(:);
    means(t).mean_VL = mean(all_VL(~isnan(all_VL)));
    means(t).std_VL = std(all_VL(~isnan(all_VL)), 0);
    means(t).mean_RF = mean(all_RF(~isnan(all_RF)));
    means(t).std_RF = std(all_RF(~isnan(all_RF)), 0);
    means(t).mean_BF = mean(all_BF(~isnan(all_BF)));
    means(t).std_BF = std(all_BF(~isnan(all_BF)), 0);
    means(t).mean_ST = mean(all_ST(~isnan(all_ST)));
    means(t).std_ST = std(all_ST(~isnan(all_ST)), 0);
    
    fprintf('  Trial %d: VL mean=%.1f%% MVC, RF mean=%.1f%% MVC\n', ...
        t, nanmax(means(t).VL), nanmax(means(t).RF));
end

%% ===== STEP 4: COMPARISON PLOTS (SIDE-BY-SIDE MUSCLES) =====

figure('Name', 'Trial Comparison', 'Color', 'w', 'Position', [100 100 1600 700]);

pgc = trial_data{1}.pgc_emg;  % Use first trial's gait cycle axis
colors = {[0.85 0.33 0.10], [0.47 0.67 0.19], [0.30 0.75 0.93]};  % Three distinct colors

muscles = {'VL', 'RF', 'BF', 'ST'};

for m = 1:4
    subplot(2, 2, m);
    hold on;
    
    for t = 1:N_Trials
        muscle_data = means(t).(muscles{m});
        muscle_sd = means(t).(sprintf('%s_sd', muscles{m}));
        
        % Plot mean with filled SD band
        fill([pgc; flipud(pgc)], ...
             [muscle_data - muscle_sd; flipud(muscle_data + muscle_sd)], ...
             colors{t}, 'FaceAlpha', 0.15, 'EdgeColor', 'none');
        
        % Plot mean line
        plot(pgc, muscle_data, 'Color', colors{t}, 'LineWidth', 2.5, ...
            'DisplayName', trial_names{t});
    end
    
    xlabel('Gait Cycle (%)');
    ylabel('% MVC');
    title(muscles{m}, 'FontSize', 12, 'FontWeight', 'bold');
    xlim([0 100]);
    ylim([0 inf]);
    grid on; box off;
    legend('Location', 'best');
end

sgtitle(sprintf('Muscle Activity Comparison - 3 Trials (%% MVC)', ...
    sprintf('%s vs %s vs %s', trial_names{1}, trial_names{2}, trial_names{3})));

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

% %% ===== STEP 6: MEAN EMG REDUCTION AND GROUPED BAR PLOT =====
% 
% muscle_means = [
%     means(1).mean_VL, means(2).mean_VL, means(3).mean_VL; 
%     means(1).mean_RF, means(2).mean_RF, means(3).mean_RF; 
%     means(1).mean_BF, means(2).mean_BF, means(3).mean_BF; 
%     means(1).mean_ST, means(2).mean_ST, means(3).mean_ST];
% 
% muscle_sds = [
%     means(1).std_VL, means(2).std_VL, means(3).std_VL; 
%     means(1).std_RF, means(2).std_RF, means(3).std_RF; 
%     means(1).std_BF, means(2).std_BF, means(3).std_BF; 
%     means(1).std_ST, means(2).std_ST, means(3).std_ST];
% 
% condition_labels = trial_names;
% condition_keys = lower(strrep(strrep(strrep(condition_labels, '-', '_'), ' ', '_'), '.', '_'));
% noexo_idx = find(contains(condition_keys, 'noexo') | contains(condition_keys, 'no_exo') | contains(condition_keys, 'no-exo'), 1);
% exoactive_idx = find(contains(condition_keys, 'exoactive') | contains(condition_keys, 'exo_active') | contains(condition_keys, 'exo-active') | contains(condition_keys, 'active'), 1);
% 
% if ~isempty(noexo_idx) && ~isempty(exoactive_idx)
%     reduction_pct = (muscle_means(:, noexo_idx) - muscle_means(:, exoactive_idx)) ./ muscle_means(:, noexo_idx) * 100;
%     fprintf('="*80\n');
%     fprintf('MEAN EMG REDUCTION FROM NOEXO TO EXOACTIVE\n');
%     fprintf('="*80\n\n');
%     for m = 1:4
%         fprintf('%s: %.1f%% reduction\n', muscles{m}, reduction_pct(m));
%     end
%     fprintf('\n');
% else
%     warning('Could not identify both noexo and exoactive conditions from trial labels. Mean EMG reduction not computed.');
% end
% 
% figure('Name', 'Mean EMG Across Conditions', 'Color', 'w', 'Position', [200 200 1000 600]);
% bar_handle = bar(muscle_means, 'grouped');
% hold on;
% 
% ngroups = size(muscle_means, 1);
% nbars = size(muscle_means, 2);
% groupwidth = min(0.8, nbars/(nbars + 1.5));
% for i = 1:nbars
%     x = (1:ngroups) - groupwidth/2 + (2*i-1) * groupwidth / (2*nbars);
%     errorbar(x, muscle_means(:, i), muscle_sds(:, i), 'k', 'linestyle', 'none', 'LineWidth', 1.2);
% end
% 
% set(gca, 'XTick', 1:4, 'XTickLabel', muscles);
% xlabel('Muscle');
% ylabel('Mean EMG (% MVC)');
% title('Mean EMG Across Conditions with Standard Deviation');
% legend(condition_labels, 'Location', 'northeastoutside');
% grid on;
% 
%% %% ===== STEP 6: MEAN EMG REDUCTION AND GROUPED BAR PLOT (WITH SEM) =====
% 1. Extract Overall Means
muscle_means = [
    means(1).mean_VL, means(2).mean_VL, means(3).mean_VL; 
    means(1).mean_RF, means(2).mean_RF, means(3).mean_RF; 
    means(1).mean_BF, means(2).mean_BF, means(3).mean_BF; 
    means(1).mean_ST, means(2).mean_ST, means(3).mean_ST];

% 2. Calculate Standard Error of the Mean (SEM = STD / sqrt(N_cycles))
% This dynamically pulls the number of strides loaded in Step 2
muscle_sems = [
    means(1).std_VL / sqrt(trial_data{1}.n_cycles), means(2).std_VL / sqrt(trial_data{2}.n_cycles), means(3).std_VL / sqrt(trial_data{3}.n_cycles); 
    means(1).std_RF / sqrt(trial_data{1}.n_cycles), means(2).std_RF / sqrt(trial_data{2}.n_cycles), means(3).std_RF / sqrt(trial_data{3}.n_cycles); 
    means(1).std_BF / sqrt(trial_data{1}.n_cycles), means(2).std_BF / sqrt(trial_data{2}.n_cycles), means(3).std_BF / sqrt(trial_data{3}.n_cycles); 
    means(1).std_ST / sqrt(trial_data{1}.n_cycles), means(2).std_ST / sqrt(trial_data{2}.n_cycles), means(3).std_ST / sqrt(trial_data{3}.n_cycles)];

% 3. Calculate Reductions
condition_labels = trial_names;
condition_keys = lower(strrep(strrep(strrep(condition_labels, '-', '_'), ' ', '_'), '.', '_'));
noexo_idx = find(contains(condition_keys, 'noexo') | contains(condition_keys, 'no_exo') | contains(condition_keys, 'no-exo'), 1);
exoactive_idx = find(contains(condition_keys, 'exoactive') | contains(condition_keys, 'exo_active') | contains(condition_keys, 'exo-active') | contains(condition_keys, 'active'), 1);

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

% 4. Plot Grouped Bar Chart with SEM Error Bars
% figure('Name', 'Mean EMG Across Conditions', 'Color', 'w', 'Position', [200 200 1000 600]);
% bar_handle = bar(muscle_means, 'grouped');
% hold on;
% 
% % Add SEM error bars correctly centered on the grouped bars
% ngroups = size(muscle_means, 1);
% nbars = size(muscle_means, 2);
% groupwidth = min(0.8, nbars/(nbars + 1.5));
% for i = 1:nbars
%     x = (1:ngroups) - groupwidth/2 + (2*i-1) * groupwidth / (2*nbars);
%     errorbar(x, muscle_means(:, i), muscle_sems(:, i), 'k', 'linestyle', 'none', 'LineWidth', 1.2);
% end
% 
% set(gca, 'XTick', 1:4, 'XTickLabel', muscles);
% xlabel('Muscle', 'FontWeight', 'bold');
% ylabel('Mean EMG (% MVC)', 'FontWeight', 'bold');
% title('Mean EMG Across Conditions (Mean \pm SEM)');
% legend(condition_labels, 'Location', 'northeastoutside');
% grid on;

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
%% %% ===== STEP 8: COMBINED FUNCTIONAL ZONE ANALYSIS (SIMPLIFIED) =====
fprintf('\n\n');
fprintf('="*80\n');
fprintf('COMBINED ZONE ANALYSIS: MEANS & REDUCTIONS\n');
fprintf('="*80\n\n');

% 1. Define Combined Gait Cycle Indices based on the pgc array (0-100%)
% Extensors active during: 13-37% OR 68-100%
idx_ext_combined = (pgc >= 13 & pgc < 37) | (pgc >= 68 & pgc <= 100);

% Flexors active during: 0-13% OR 37-68%
idx_flex_combined = (pgc >= 0 & pgc < 13) | (pgc >= 37 & pgc < 68);

% Initialize struct to hold zone metrics across trials
z_metrics = struct();

for t = 1:N_Trials
    % Recreate normalized matrices to calculate stride-to-stride variance
    VL_norm = cell2mat(trial_data{t}.emg_cycles.VL') ./ mvc_values{t}.mvc_VL * 100;
    RF_norm = cell2mat(trial_data{t}.emg_cycles.RF') ./ mvc_values{t}.mvc_RF * 100;
    BF_norm = cell2mat(trial_data{t}.emg_cycles.BF') ./ mvc_values{t}.mvc_BF * 100;
    ST_norm = cell2mat(trial_data{t}.emg_cycles.ST') ./ mvc_values{t}.mvc_ST * 100;
    
    % --- EXTENSORS (VL & RF) in Combined Extension Phase ---
    % Calculate the mean within the combined zone FOR EACH STRIDE, then take overall mean & std
    z_metrics(t).VL_ext_mean = mean(mean(VL_norm(idx_ext_combined, :), 1, 'omitnan'), 'omitnan');
    z_metrics(t).VL_ext_sd   = std(mean(VL_norm(idx_ext_combined, :), 1, 'omitnan'), 0, 'omitnan');
    
    z_metrics(t).RF_ext_mean = mean(mean(RF_norm(idx_ext_combined, :), 1, 'omitnan'), 'omitnan');
    z_metrics(t).RF_ext_sd   = std(mean(RF_norm(idx_ext_combined, :), 1, 'omitnan'), 0, 'omitnan');

    % --- FLEXORS (BF & ST) in Combined Flexion Phase ---
    z_metrics(t).BF_flex_mean = mean(mean(BF_norm(idx_flex_combined, :), 1, 'omitnan'), 'omitnan');
    z_metrics(t).BF_flex_sd   = std(mean(BF_norm(idx_flex_combined, :), 1, 'omitnan'), 0, 'omitnan');
    
    z_metrics(t).ST_flex_mean = mean(mean(ST_norm(idx_flex_combined, :), 1, 'omitnan'), 'omitnan');
    z_metrics(t).ST_flex_sd   = std(mean(ST_norm(idx_flex_combined, :), 1, 'omitnan'), 0, 'omitnan');
end

% 2. Calculate Reductions (No Exo vs Exo Active)
if ~isempty(noexo_idx) && ~isempty(exoactive_idx)
    % Helper function for percentage reduction
    calc_red = @(m_name) ((z_metrics(noexo_idx).(m_name) - z_metrics(exoactive_idx).(m_name)) / z_metrics(noexo_idx).(m_name)) * 100;
    
    fprintf('--- OVERALL REDUCTIONS (No Exo -> Exo Active) ---\n');
    fprintf('VL | Total Extension Phase: %6.2f%% reduction\n', calc_red('VL_ext_mean'));
    fprintf('RF | Total Extension Phase: %6.2f%% reduction\n', calc_red('RF_ext_mean'));
    fprintf('BF | Total Flexion Phase:   %6.2f%% reduction\n', calc_red('BF_flex_mean'));
    fprintf('ST | Total Flexion Phase:   %6.2f%% reduction\n\n', calc_red('ST_flex_mean'));
end

% 3. Plotting Setup: A single 2x2 grid for all 4 muscles
bar_colors = [0.6 0.6 0.6; 0.47 0.67 0.19; 0.30 0.75 0.93]; % Gray, Green, Blue
x_labels = categorical(trial_names);
x_labels = reordercats(x_labels, trial_names); % Keep original order

figure('Name', 'Combined Functional Zone Analysis', 'Color', 'w', 'Position', [150 150 1200 800]);

% Setup Plotting Arrays
plot_fields = {'VL_ext', 'RF_ext', 'BF_flex', 'ST_flex'};
plot_titles = {'Vastus Lateralis (VL) During Extension Phases', ...
               'Rectus Femoris (RF) During Extension Phases', ...
               'Biceps Femoris (BF) During Flexion Phases', ...
               'Semitendinosus (ST) During Flexion Phases'};

for i = 1:4
    subplot(2, 2, i); hold on;
    means_to_plot = [z_metrics(1).(sprintf('%s_mean', plot_fields{i})), ...
                     z_metrics(2).(sprintf('%s_mean', plot_fields{i})), ...
                     z_metrics(3).(sprintf('%s_mean', plot_fields{i}))];
    sds_to_plot   = [z_metrics(1).(sprintf('%s_sd', plot_fields{i})), ...
                     z_metrics(2).(sprintf('%s_sd', plot_fields{i})), ...
                     z_metrics(3).(sprintf('%s_sd', plot_fields{i}))];
                 
    b = bar(x_labels, means_to_plot, 'FaceColor', 'flat');
    b.CData = bar_colors;
    
    % Add error bars
    errorbar(1:3, means_to_plot, sds_to_plot, 'k', 'linestyle', 'none', 'LineWidth', 1.5, 'CapSize', 8);
    
    ylabel('Mean EMG (% MVC)', 'FontWeight', 'bold');
    title(plot_titles{i}, 'FontSize', 12);
    
    % Add y-axis breathing room for the error bars
    max_val = max(means_to_plot + sds_to_plot);
    ylim([0, max_val * 1.2]);
    
    grid on; box off;
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
