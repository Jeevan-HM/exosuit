%% process_all_conditions.m
% Batch processes 12 datasets in SelectCycles folder
% Extracts average EMG (Mean) for predefined functional zones
% Saves results into All_Conditions_Summary.mat
% Allows user to visualize one representative condition

clear all; close all; clc;

fprintf('="*80\n');
fprintf('BATCH PROCESSING - ALL CONDITIONS (MEAN EMG)\n');
fprintf('="*80\n\n');

%% ===== CONFIGURATION =====
data_dir = fullfile(pwd, 'SelectCycles');
if ~exist(data_dir, 'dir')
    error('SelectCycles directory not found in the current folder.');
end

% Hardcoded MVC values
mvc.mvc_VL = 3.10726e-05;  
mvc.mvc_RF = 3.72490e-05;   
mvc.mvc_BF = 3.0036e-05; 
mvc.mvc_ST =  2.0456e-05; 


% Define walking conditions and exosuit conditions
walking_conditions = {'inc0_spd0.8', 'inc0_spd1.2', 'inc5_spd0.8', 'inc5_spd1.2'};
exo_conditions = {'noexo', 'inactive', 'active_rl'};
exo_labels = {'No Exo', 'Inactive', 'Active RL'};
muscles = {'VL', 'RF', 'BF', 'ST'};

% Initialize summary struct array
all_conditions_results = struct();

%% ===== BATCH PROCESSING =====

for w_idx = 1:length(walking_conditions)
    walk_cond = walking_conditions{w_idx};
    fprintf('Processing Walking Condition: %s\n', walk_cond);
    
    all_conditions_results(w_idx).condition_name = walk_cond;
    
    % Store trial data for visualization if needed
    trial_data_cache = cell(1, 3);
    means_cache = struct();
    z_metrics = struct();
    
    for e_idx = 1:length(exo_conditions)
        exo_cond = exo_conditions{e_idx};
        
        % Find the file matching this walking and exo condition
        search_pattern = sprintf('Processed_%s_%s*.mat', walk_cond, exo_cond);
        if strcmp(exo_cond, 'active_rl')
            search_pattern = sprintf('Processed_%s_active_rl*.mat', walk_cond);
        end
        
        files = dir(fullfile(data_dir, search_pattern));
        if isempty(files)
            warning('File not found for %s - %s. Skipping.', walk_cond, exo_cond);
            continue;
        end
        
        filepath = fullfile(data_dir, files(1).name);
        fprintf('  Loaded: %s\n', files(1).name);
        
        data = load(filepath, 'emg_cycles', 'knee_cycles', 'pgc_emg', 'n_cycles');
        trial_data_cache{e_idx} = data;
        
        % Normalize to MVC
        VL_norm = cell2mat(data.emg_cycles.VL') ./ mvc.mvc_VL * 100;
        RF_norm = cell2mat(data.emg_cycles.RF') ./ mvc.mvc_RF * 100;
        BF_norm = cell2mat(data.emg_cycles.BF') ./ mvc.mvc_BF * 100;
        ST_norm = cell2mat(data.emg_cycles.ST') ./ mvc.mvc_ST * 100;
        
        % Store basic means for plotting Continuous Traces (similar to compare_trials.m)
        means_cache(e_idx).VL = mean(VL_norm, 2, 'omitnan');
        means_cache(e_idx).VL_sd = std(VL_norm, 0, 2, 'omitnan');
        means_cache(e_idx).RF = mean(RF_norm, 2, 'omitnan');
        means_cache(e_idx).RF_sd = std(RF_norm, 0, 2, 'omitnan');
        means_cache(e_idx).BF = mean(BF_norm, 2, 'omitnan');
        means_cache(e_idx).BF_sd = std(BF_norm, 0, 2, 'omitnan');
        means_cache(e_idx).ST = mean(ST_norm, 2, 'omitnan');
        means_cache(e_idx).ST_sd = std(ST_norm, 0, 2, 'omitnan');
        
        % Compute Zonal Analysis (Mean EMG in Functional Zones)
        pgc = data.pgc_emg;
        idx_ext_combined = (pgc >= 13 & pgc < 37) | (pgc >= 68 & pgc <= 100);
        idx_flex_combined = (pgc >= 0 & pgc < 13) | (pgc >= 37 & pgc < 68);
        
        z_metrics(e_idx).exo_cond = exo_cond;
        
        z_metrics(e_idx).VL_ext_mean = mean(mean(VL_norm(idx_ext_combined, :), 1, 'omitnan'), 'omitnan');
        z_metrics(e_idx).VL_ext_sd   = std(mean(VL_norm(idx_ext_combined, :), 1, 'omitnan'), 0, 'omitnan');
        
        z_metrics(e_idx).RF_ext_mean = mean(mean(RF_norm(idx_ext_combined, :), 1, 'omitnan'), 'omitnan');
        z_metrics(e_idx).RF_ext_sd   = std(mean(RF_norm(idx_ext_combined, :), 1, 'omitnan'), 0, 'omitnan');

        z_metrics(e_idx).BF_flex_mean = mean(mean(BF_norm(idx_flex_combined, :), 1, 'omitnan'), 'omitnan');
        z_metrics(e_idx).BF_flex_sd   = std(mean(BF_norm(idx_flex_combined, :), 1, 'omitnan'), 0, 'omitnan');
        
        z_metrics(e_idx).ST_flex_mean = mean(mean(ST_norm(idx_flex_combined, :), 1, 'omitnan'), 'omitnan');
        z_metrics(e_idx).ST_flex_sd   = std(mean(ST_norm(idx_flex_combined, :), 1, 'omitnan'), 0, 'omitnan');
    end
    
    % Store in global struct
    all_conditions_results(w_idx).means_cache = means_cache;
    all_conditions_results(w_idx).z_metrics = z_metrics;
    all_conditions_results(w_idx).pgc = pgc;
    fprintf('\n');
end

%% ===== SAVE RESULTS =====
save_path = fullfile(pwd, 'All_Conditions_Summary.mat');
save(save_path, 'all_conditions_results', 'walking_conditions', 'exo_conditions', 'exo_labels');
fprintf('="*80\n');
fprintf('Data successfully saved to %s\n', save_path);
fprintf('="*80\n\n');


%% ===== VISUALIZATION SELECTION =====

[sel_idx, tf] = listdlg('PromptString', 'Select a condition to visualize:', ...
                        'SelectionMode', 'single', ...
                        'ListString', walking_conditions, ...
                        'Name', 'Visualize Condition');

if tf
    % User selected a condition
    vis_cond_name = walking_conditions{sel_idx};
    vis_data = all_conditions_results(sel_idx);
    
    fprintf('Visualizing %s...\n', vis_cond_name);
    
    % 1. Plot Continuous Traces
    figure('Name', sprintf('Continuous EMG - %s', vis_cond_name), 'Color', 'w', 'Position', [100 100 1600 700]);
    colors = {[0.85 0.33 0.10], [0.47 0.67 0.19], [0.30 0.75 0.93]}; 
    pgc = vis_data.pgc;
    
    for m = 1:4
        subplot(2, 2, m);
        hold on;
        
        for e_idx = 1:3
            muscle_data = vis_data.means_cache(e_idx).(muscles{m});
            muscle_sd = vis_data.means_cache(e_idx).(sprintf('%s_sd', muscles{m}));
            
            fill([pgc; flipud(pgc)], ...
                 [muscle_data - muscle_sd; flipud(muscle_data + muscle_sd)], ...
                 colors{e_idx}, 'FaceAlpha', 0.15, 'EdgeColor', 'none');
            
            plot(pgc, muscle_data, 'Color', colors{e_idx}, 'LineWidth', 2.5, ...
                'DisplayName', exo_labels{e_idx});
        end
        
        xlabel('Gait Cycle (%)');
        ylabel('% MVC');
        title(muscles{m}, 'FontSize', 12, 'FontWeight', 'bold');
        xlim([0 100]);
        ylim([0 inf]);
        grid on; box off;
        legend('Location', 'best');
    end
    sgtitle(sprintf('Muscle Activity Comparison (%% MVC) - %s', vis_cond_name), 'FontSize', 15, 'FontWeight', 'bold');
    
    
    % 2. Plot Bar Charts for Zonal Analysis (Mean EMG)
    bar_colors = [0.6 0.6 0.6; 0.47 0.67 0.19; 0.30 0.75 0.93]; % Gray, Green, Blue
    x_labels = categorical(exo_labels);
    x_labels = reordercats(x_labels, exo_labels);
    
    figure('Name', sprintf('Functional Zone Analysis - %s', vis_cond_name), 'Color', 'w', 'Position', [150 150 1200 800]);

    plot_fields = {'VL_ext', 'RF_ext', 'BF_flex', 'ST_flex'};
    plot_titles = {'Vastus Lateralis (VL) During Extension Phases', ...
                   'Rectus Femoris (RF) During Extension Phases', ...
                   'Biceps Femoris (BF) During Flexion Phases', ...
                   'Semitendinosus (ST) During Flexion Phases'};

    for i = 1:4
        subplot(2, 2, i); hold on;
        means_to_plot = [vis_data.z_metrics(1).(sprintf('%s_mean', plot_fields{i})), ...
                         vis_data.z_metrics(2).(sprintf('%s_mean', plot_fields{i})), ...
                         vis_data.z_metrics(3).(sprintf('%s_mean', plot_fields{i}))];
        sds_to_plot   = [vis_data.z_metrics(1).(sprintf('%s_sd', plot_fields{i})), ...
                         vis_data.z_metrics(2).(sprintf('%s_sd', plot_fields{i})), ...
                         vis_data.z_metrics(3).(sprintf('%s_sd', plot_fields{i}))];
                     
        b = bar(x_labels, means_to_plot, 'FaceColor', 'flat');
        b.CData = bar_colors;
        
        errorbar(1:3, means_to_plot, sds_to_plot, 'k', 'linestyle', 'none', 'LineWidth', 1.5, 'CapSize', 8);
        
        ylabel('Mean EMG (% MVC)', 'FontWeight', 'bold');
        title(plot_titles{i}, 'FontSize', 12);
        
        max_val = max(means_to_plot + sds_to_plot);
        if isnan(max_val) || max_val == 0
            max_val = 1;
        end
        ylim([0, max_val * 1.2]);
        
        grid on; box off;
    end
    sgtitle(sprintf('Targeted Muscle Activity During Functional Phases - %s', vis_cond_name), 'FontSize', 15, 'FontWeight', 'bold');
    
else
    fprintf('No condition selected for visualization.\n');
end

fprintf('Done.\n');
