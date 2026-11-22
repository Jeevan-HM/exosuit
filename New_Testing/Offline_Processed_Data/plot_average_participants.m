%% plot_average_participants.m
% Aggregates average EMG data across all participants and conditions
% Generates a single, unified trend plot for all 4 walking conditions
% Uses shaded error regions around continuous lines.

clear all; close all; clc;

%% ===== CONFIGURATION =====
% Automatically finds the base directory containing the script
base_dir = fileparts(mfilename('fullpath'));
if isempty(base_dir)
    base_dir = pwd;
end

subjects = {'Amir', 'Jeevan', 'Mason', 'Ruthvik'};

% Ordered from easiest to hardest
walking_conditions = {'inc0spd0p8', 'inc0spd1p2', 'inc5spd0p8', 'inc5spd1p2'};
walking_labels = {'0% Inc,\n0.8 m/s', '0% Inc,\n1.2 m/s', '5% Inc,\n0.8 m/s', '5% Inc,\n1.2 m/s'};

% The data in .mat files is stored in order: 1=Active, 2=Inactive, 3=No Exo
num_exo = 3;

% Target plotting labels (from Left to Right)
exo_labels = {'No Exosuit', 'Exosuit Inactive', 'Exosuit Active'};
muscles = {'VL', 'RF', 'BF', 'ST'};
metrics_fields_mean = {'VL_ext_mean', 'RF_ext_mean', 'BF_flex_mean', 'ST_flex_mean'};
metrics_fields_sd   = {'VL_ext_sd',   'RF_ext_sd',   'BF_flex_sd',   'ST_flex_sd'};

plot_titles = {'Vastus Lateralis (VL)', ...
               'Rectus Femoris (RF)', ...
               'Biceps Femoris (BF)', ...
               'Semitendinosus (ST)'};

% Colors: Orange (No Exo), Green (Inactive), Blue (Active)
bar_colors = [0.85 0.33 0.10; 0.47 0.67 0.19; 0.30 0.75 0.93]; 

% Initialize 4D arrays to store all data: (Walking x Participant x Exo x Muscle)
num_walk = length(walking_conditions);
num_subj = length(subjects);
num_musc = length(muscles);

all_data_mean = nan(num_walk, num_subj, num_exo, num_musc);
all_data_sd   = nan(num_walk, num_subj, num_exo, num_musc);

%% ===== DATA AGGREGATION =====
fprintf('="*80\n');
fprintf('AGGREGATING PARTICIPANT DATA\n');
fprintf('="*80\n\n');

for w_idx = 1:num_walk
    walk_cond = walking_conditions{w_idx};
    fprintf('Loading %s...\n', walk_cond);
    
    for s_idx = 1:num_subj
        subj = subjects{s_idx};
        
        filepath = fullfile(base_dir, subj, 'SelectCycles', 'MeanSTDs', sprintf('%s.mat', walk_cond));
        
        if exist(filepath, 'file')
            data = load(filepath, 'z_metrics');
            
            if isfield(data, 'z_metrics')
                for e_idx = 1:num_exo
                    for m_idx = 1:num_musc
                        % Load Mean
                        field_name_mean = metrics_fields_mean{m_idx};
                        if isfield(data.z_metrics(e_idx), field_name_mean)
                            all_data_mean(w_idx, s_idx, e_idx, m_idx) = data.z_metrics(e_idx).(field_name_mean);
                        end
                        
                        % Load SD
                        field_name_sd = metrics_fields_sd{m_idx};
                        if isfield(data.z_metrics(e_idx), field_name_sd)
                            all_data_sd(w_idx, s_idx, e_idx, m_idx) = data.z_metrics(e_idx).(field_name_sd);
                        end
                    end
                end
            end
        end
    end
end

%% ===== PROCESS GRAND AVERAGES =====
fprintf('\nGenerating unified figure...\n');

% 1. Average across participants -> (Walking x Exo x Muscle)
grand_means = squeeze(mean(all_data_mean, 2, 'omitnan')); 
grand_sds   = squeeze(mean(all_data_sd, 2, 'omitnan'));   

% 2. FLIP THE EXO ORDER from [Active, Inactive, No Exo] to [No Exo, Inactive, Active]
reorder_idx = [3, 2, 1];
grand_means = grand_means(:, reorder_idx, :);
grand_sds   = grand_sds(:, reorder_idx, :);

%% ===== UNIFIED TREND PLOTTING =====

figure('Name', 'Unified Trend Comparison', 'Color', 'w', 'Position', [100 100 1800 600]);

x_vals = 1:num_walk;
h_lines = zeros(1, num_exo); % For legend

for m_idx = 1:num_musc
    subplot(1, 4, m_idx); hold on;
    
    musc_means = grand_means(:, :, m_idx); % 4x3 matrix
    musc_sds   = grand_sds(:, :, m_idx);   % 4x3 matrix
    
    % Step 1: Draw all shaded error bands first (so they stay in the background)
    for e_idx = 1:num_exo
        y_mean = musc_means(:, e_idx)';
        y_err  = musc_sds(:, e_idx)';
        
        % Filter out NaNs to prevent patch drawing errors if data is missing
        valid_idx = ~isnan(y_mean) & ~isnan(y_err);
        if any(valid_idx)
            x_valid = x_vals(valid_idx);
            y_valid = y_mean(valid_idx);
            err_valid = y_err(valid_idx);
            
            fill([x_valid, fliplr(x_valid)], ...
                 [y_valid + err_valid, fliplr(y_valid - err_valid)], ...
                 bar_colors(e_idx, :), 'FaceAlpha', 0.15, 'EdgeColor', 'none');
        end
    end
    
    % Step 2: Draw the solid lines and points on top
    for e_idx = 1:num_exo
        y_mean = musc_means(:, e_idx)';
        
        h_lines(e_idx) = plot(x_vals, y_mean, '-o', ...
            'Color', bar_colors(e_idx, :), ...
            'LineWidth', 3, ...
            'MarkerSize', 10, ...
            'MarkerFaceColor', bar_colors(e_idx, :), ...
            'MarkerEdgeColor', 'w');
    end
    
    % Formatting
    % Using sprintfc to process the \n newlines in labels
    set(gca, 'XTick', x_vals, 'XTickLabel', compose(walking_labels));
    xlim([0.8, num_walk + 0.2]);
    
    % Get reasonable Y-limits
    max_val = max(musc_means(:) + musc_sds(:));
    if isnan(max_val) || max_val == 0
        max_val = 1;
    end
    ylim([0, max_val * 1.1]);
    
    title(plot_titles{m_idx}, 'FontSize', 16);
    if m_idx == 1
        ylabel('Mean EMG (% MVC)', 'FontWeight', 'bold');
    end
    
    fontsize(gcf, 20, "points");
    grid on; box off;
end

% Add a single global legend at the bottom
% Note: Using the last subplot to anchor the legend, placing it southoutside
% lgd = legend(h_lines, exo_labels, 'Orientation', 'horizontal', 'Location', 'southoutside');
% lgd.NumColumns = 3;
% % Move legend slightly down to span across the figure bottom if desired, 
% % or keep it relative to the last subplot. A simple 'Position' tweak works too.
% lgd.Position(1) = 0.5 - lgd.Position(3)/2; % Center it horizontally

sgtitle(sprintf('Muscle Activity Trends Across Varying Terrains (N=%d Participants)', num_subj), ...
    'FontSize', 24, 'FontWeight', 'bold');

%% ===== PERCENTAGE REDUCTION PLOTTING =====
fprintf('\nGenerating percentage reduction figure...\n');

% Calculate % reduction for each participant: (NoExo - Active) / NoExo * 100
% all_data_mean is (Walk x Participant x Exo x Muscle)
% Exo order in all_data_mean: 1=Active, 2=Inactive, 3=No Exo
no_exo_data = squeeze(all_data_mean(:, :, 3, :)); % (Walk x Participant x Muscle)
active_data = squeeze(all_data_mean(:, :, 1, :)); % (Walk x Participant x Muscle)

pct_reduction = (no_exo_data - active_data) ./ no_exo_data * 100;

% Mean and Inter-Subject SD of the reduction
mean_red = squeeze(mean(pct_reduction, 2, 'omitnan')); % (Walk x Muscle)
sd_red = squeeze(std(pct_reduction, 0, 2, 'omitnan')); % (Walk x Muscle)

figure('Name', 'Percentage Reduction (No Exo vs Active)', 'Color', 'w', 'Position', [150 150 1800 600]);

for m_idx = 1:num_musc
    subplot(1, 4, m_idx); hold on;
    
    y_mean = mean_red(:, m_idx); % 4x1
    y_sd = sd_red(:, m_idx);     % 4x1
    
    % Use the Active condition color (Blue) for the reduction bars
    b = bar(x_vals, y_mean, 'FaceColor', bar_colors(3, :), 'EdgeColor', 'none', 'BarWidth', 0.6);
    
    % Add error bars showing inter-subject variability
    errorbar(x_vals, y_mean, y_sd, 'k', 'linestyle', 'none', ...
        'LineWidth', 2, 'CapSize', 10);
        
    % Formatting
    set(gca, 'XTick', x_vals, 'XTickLabel', compose(walking_labels));
    xlim([0.5, num_walk + 0.5]);
    
    % Get reasonable Y-limits
    max_val = max(y_mean + y_sd);
    min_val = min(0, min(y_mean - y_sd));
    if isnan(max_val), max_val = 1; end
    if isnan(min_val), min_val = 0; end
    ylim([min_val - 5, max_val + 5]);
    
    title(plot_titles{m_idx}, 'FontSize', 16);
    if m_idx == 1
        ylabel('EMG Reduction (%)', 'FontWeight', 'bold');
    end
    
    fontsize(gcf, 20, "points");
    grid on; box off;
end

sgtitle(sprintf('Percentage Reduction in Muscle Activity (No Exo -> Active)\nError bars = Inter-Subject Standard Deviation (N=%d)', num_subj), ...
    'FontSize', 24, 'FontWeight', 'bold');

fprintf('="*80\n');
fprintf('Processing complete.\n');
fprintf('="*80\n');
