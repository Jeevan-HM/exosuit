clc; clear; warning off;
%%

% Define files
files = {
    "RL_TrainingData_Par_EXOACTIVE_RL_inc5_spd1p2_1", 
    "RL_TrainingData_Par_EXOACTIVE_RL_inc5_spd1p2_1",
};
%%
data_range = [7 38;...
                13 44];

%%
% Define constants
ranges = [0.05, 0.2; 0.35, 0.55; 0.65, 0.85];  % for denormalization
coeff_state_timing = 1;
coeff_kine = 0.5;
coeff_action = 0.5;
coeff_emg = 0.4;
threshold = 2;  % same for all

% Initialize storage
cost_cells = {};

for f = 1:length(files)
    data = readtable(files{f});
    [state_matrix, emg_state] = parse_state_column(data(:,11), data(:,12:15));
    denorm = denormalize_states(state_matrix(:,1:3), ranges);
    [ta_err, tb_err, tc_err, kineA, kineC, act_err] = compute_errors(data, denorm);

    cost = compute_cost(ta_err, tb_err, tc_err, kineA, kineC, act_err, emg_state, ...
                        coeff_state_timing, coeff_kine, coeff_action, coeff_emg);

    % Clean cost
    cost_clean = cost(cost <= threshold);

    % Store selected samples
    cost_cells{f} = cost_clean(data_range(f,1):data_range(f,2)) / 1.2;

    % Optional: plot individual trial
    figure; plot(1:length(cost_clean), cost_clean, 'b'); title(['Trial ', num2str(f)]);
end

all_costs = pad_to_matrix(cost_cells);

% --- Plot mean ± 95% CI ---
mean_vals = mean(all_costs, 2, 'omitnan');
sem = std(all_costs, 0, 2, 'omitnan') ./ sqrt(sum(~isnan(all_costs), 2));
ci95 = 1.96 * sem;
ci95(isnan(ci95)) = 0; % Prevent NaN in fill if std is NaN
x = (1:size(all_costs, 1))';

figure; hold on;
fill([x', fliplr(x')], ...
     [mean_vals' + ci95', fliplr(mean_vals' - ci95')], ...
     [0.8 0.8 1], 'EdgeColor', 'none', 'FaceAlpha', 0.5);
plot(x, mean_vals, 'b', 'LineWidth', 2);
xlabel('Sample'); ylabel('Cost'); title('Training Cost (Mean ± 95% CI)'); grid on;

%%
% data_range = [7 37;...
%                  22 52];

% Define EMG threshold
emg_threshold = 10;
% Initialize storage
emg_cells = {};

for f = 1:length(files)
    data = readtable(files{f});
    [~, emg_state] = parse_state_column(data(:,11), data(:,12:15));
    emg_clean = emg_state(emg_state <= emg_threshold);
    emg_cells{f} = emg_clean(data_range(f,1):data_range(f,2)) / 1.5;

    % Optional individual plot
    figure; plot(1:length(emg_cells{f}), emg_cells{f}, 'm'); title(['EMG Trial ', num2str(f)]);
end

all_emgs = pad_to_matrix(emg_cells);

% Plot EMG mean ± 95% CI
mean_emg = mean(all_emgs, 2, 'omitnan');
sem_emg = std(all_emgs, 0, 2, 'omitnan') ./ sqrt(sum(~isnan(all_emgs), 2));
ci95_emg = 1.96 * sem_emg;
ci95_emg(isnan(ci95_emg)) = 0;
x = (1:size(all_emgs, 1))';

figure; hold on;
fill([x', fliplr(x')], ...
     [mean_emg' + ci95_emg', fliplr(mean_emg' - ci95_emg')], ...
     [1 0.8 0.8], 'EdgeColor', 'none', 'FaceAlpha', 0.5);
plot(x, mean_emg, 'r', 'LineWidth', 2);
xlabel('Sample'); ylabel('EMG State');
title('EMG Mean ± 95% CI'); grid on;

%%
% Define thresholds
kineA_threshold = 3;
kineC_threshold = 3;

% Initialize storage
kineA_cells = {};
kineC_cells = {};

for f = 1:length(files)
    data = readtable(files{f});

    % Extract and clean Kinematic A
    kineA = table2array(data(:,7));
    kineA_clean = kineA(kineA <= kineA_threshold);
    kineA_cells{f} = kineA_clean(data_range(f,1):data_range(f,2));

    % Extract and clean Kinematic C
    kineC = table2array(data(:,8)) + 0.4;
    kineC_clean = kineC(kineC <= kineC_threshold);
    kineC_cells{f} = kineC_clean(data_range(f,1):data_range(f,2));
end

all_kineA = pad_to_matrix(kineA_cells);
all_kineC = pad_to_matrix(kineC_cells);

x_A = (1:size(all_kineA, 1))';
x_C = (1:size(all_kineC, 1))';

% --- Subplot 1: Kinematic A ---
mean_kineA = mean(all_kineA, 2, 'omitnan');
sem_kineA = std(all_kineA, 0, 2, 'omitnan') ./ sqrt(sum(~isnan(all_kineA), 2));
ci95_kineA = 1.96 * sem_kineA;
ci95_kineA(isnan(ci95_kineA)) = 0;

% --- Subplot 2: Kinematic C ---
mean_kineC = mean(all_kineC, 2, 'omitnan');
sem_kineC = std(all_kineC, 0, 2, 'omitnan') ./ sqrt(sum(~isnan(all_kineC), 2));
ci95_kineC = 1.96 * sem_kineC;
ci95_kineC(isnan(ci95_kineC)) = 0;

% --- Plot both in subplots ---
figure;

% Subplot 1: Kine A
subplot(2,1,1); hold on;
fill([x_A', fliplr(x_A')], ...
     [mean_kineA' + ci95_kineA', fliplr(mean_kineA' - ci95_kineA')], ...
     [0.8 1 0.8], 'EdgeColor', 'none', 'FaceAlpha', 0.5);
plot(x_A, mean_kineA, 'g', 'LineWidth', 2);
ylabel('Kinematic Error A');
title('Kinematic A Mean ± 95% CI'); grid on;

% Subplot 2: Kine C
subplot(2,1,2); hold on;
fill([x_C', fliplr(x_C')], ...
     [mean_kineC' + ci95_kineC', fliplr(mean_kineC' - ci95_kineC')], ...
     [0.8 1 1], 'EdgeColor', 'none', 'FaceAlpha', 0.5);
plot(x_C, mean_kineC, 'c', 'LineWidth', 2);
xlabel('Sample'); ylabel('Kinematic Error C');
title('Kinematic C Mean ± 95% CI'); grid on;
%%
save('inc5spd1p2.mat', 'all_costs', 'all_emgs', 'all_kineA','all_kineC');

%%
function padded = pad_to_matrix(cell_array)
    max_len = max(cellfun(@length, cell_array));
    num_cols = length(cell_array);
    padded = NaN(max_len, num_cols);
    for i = 1:num_cols
        padded(1:length(cell_array{i}), i) = cell_array{i};
    end
end

function [state_matrix, emg_state] = parse_state_column(state_col, emg_cols)
    % Convert string to numeric matrix
    state_strs = table2array(state_col);
    state_matrix = zeros(numel(state_strs), 5);
    for i = 1:numel(state_strs)
        % Remove Python/NumPy specific syntax
        clean_str = strrep(state_strs{i}, 'np.float64(', '');
        clean_str = strrep(clean_str, ')', '');
        
        state_matrix(i, :) = str2num(clean_str); %#ok<ST2NM>
    end
    emg_state = sum(table2array(emg_cols), 2);
end

function denorm = denormalize_states(state_matrix, ranges)
    denorm = zeros(size(state_matrix));
    for i = 1:3
        a = ranges(i, 1);
        b = ranges(i, 2);
        denorm(:, i) = state_matrix(:, i) * (b - a) + a;
    end
end

function [ta, tb, tc, kineA, kineC, act_err] = compute_errors(data, denorm)
    ta = denorm(:,1) - 0.16;
    tb = denorm(:,2) - 0.4;
    tc = denorm(:,3) - 0.75;
    kineA = table2array(data(:,7));
    kineC = table2array(data(:,8)) + 0.4;
    act_cols = table2array(data(:,3:6));
    act_err = sum(act_cols.^2, 2);
end

function cost = compute_cost(ta, tb, tc, kineA, kineC, act_err, emg, ...
                             c1, c2, c3, c4)
    timing_err = ta.^2 + tb.^2 + tc.^2;
    kine_err = kineA.^2 + kineC.^2;
    cost = c1*timing_err + c2*kine_err + c3*act_err + c4*(emg.^2);
end