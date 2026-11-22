%% plot_representative_subject.m
% Plots the representative-subject muscle activity figure (paper Fig. 10)
% for ONE participant: four figures (one per walking condition), each a
% 1x4 subplot of VL, RF, BF, ST showing No-Exo / Inactive / Active
% mean +/- SD across strides, in % MVC over the gait cycle.
%
% Data source: this folder (Offline_Processed_Data), the same data used for
% all paper statistics. For each subject it automatically uses:
%   - the MVC values in <subject>/build_all_metrics.m (identical to that
%     subject's compare_trials.m), because Processed_*.mat files store RAW
%     envelopes (volts), not %MVC;
%   - the active RL trial recorded in <subject>_<cond>_metrics.mat
%     (metrics.active_trial_used), i.e. the same trial the statistics used.
%
% USAGE: run, pick a participant from the list (or set SUBJECT below).
% Figures are left open for manual editing; set SAVE = true to also save
% .fig + .png copies into ./representative_subject_figs/.

clear; close all; clc;

%% ===== USER SETTINGS =====
SUBJECT     = '';        % e.g. 'Amir'. Leave '' to choose from a list.
SAVE        = false;     % true -> save .fig and .png for each condition
SHOW_LABELS = true;      % axis labels / titles / legend on or off

% Walking conditions: file tag -> label used on the figure
COND_TAGS   = {'inc0_spd0.8', 'inc0_spd1.2', 'inc5_spd0.8', 'inc5_spd1.2'};
COND_LABELS = {'0% grade, 0.8 m/s', '0% grade, 1.2 m/s', ...
               '10% grade, 0.8 m/s', '10% grade, 1.2 m/s'};

MUSCLES      = {'VL', 'RF', 'BF', 'ST'};
MUSCLE_NAMES = {'Vastus Lateralis', 'Rectus Femoris', 'Biceps Femoris', 'Semitendinosus'};

% Line colours: No-Exo (orange), Inactive (green), Active (blue)
COLORS   = {[0.85 0.33 0.10], [0.47 0.67 0.19], [0.30 0.75 0.93]};
EX_NAMES = {'No Exosuit', 'Exosuit Inactive', 'Exosuit Active'};

%% ===== PICK SUBJECT =====
this_dir = fileparts(mfilename('fullpath'));
if isempty(this_dir), this_dir = pwd; end

if isempty(SUBJECT)
    d = dir(this_dir);
    d = d([d.isdir] & ~startsWith({d.name}, '.'));
    subs = {};
    for i = 1:numel(d)
        if isfile(fullfile(this_dir, d(i).name, 'build_all_metrics.m'))
            subs{end+1} = d(i).name; %#ok<AGROW>
        end
    end
    if isempty(subs), error('No subject folders with build_all_metrics.m found in %s', this_dir); end
    [idx, ok] = listdlg('PromptString', 'Select participant:', 'SelectionMode', 'single', ...
                        'ListString', subs, 'ListSize', [220 180]);
    if ~ok, error('No participant selected.'); end
    SUBJECT = subs{idx};
end
subj_dir = fullfile(this_dir, SUBJECT);
fprintf('Participant: %s\n', SUBJECT);

%% ===== MVC VALUES (parsed from the subject's build_all_metrics.m) =====
mvc = read_mvc(fullfile(subj_dir, 'build_all_metrics.m'), MUSCLES);
fprintf('MVC (V): VL=%.3g  RF=%.3g  BF=%.3g  ST=%.3g\n', mvc.VL, mvc.RF, mvc.BF, mvc.ST);

%% ===== ONE FIGURE PER WALKING CONDITION =====
if SAVE
    out_dir = fullfile(this_dir, 'representative_subject_figs');
    if ~exist(out_dir, 'dir'), mkdir(out_dir); end
end

for c = 1:numel(COND_TAGS)
    tag = COND_TAGS{c};

    % --- files for the three exosuit conditions ---
    f_noexo = fullfile(subj_dir, sprintf('Processed_%s_noexo_trial1.mat', tag));
    f_inact = fullfile(subj_dir, sprintf('Processed_%s_inactive_trial1.mat', tag));
    f_active = active_trial_file(subj_dir, SUBJECT, tag);
    files = {f_noexo, f_inact, f_active};

    missing = files(~cellfun(@isfile, files));
    if ~isempty(missing)
        warning('%s | %s: missing file(s), skipping:\n  %s', SUBJECT, tag, strjoin(missing, '\n  '));
        continue;
    end

    % --- load, normalize to %MVC, mean +/- SD across strides ---
    avg = cell(1, 3);  sdv = cell(1, 3);  ncyc = zeros(1, 3);
    for e = 1:3
        D = load(files{e}, 'emg_cycles', 'pgc_emg', 'n_cycles');
        pgc = D.pgc_emg(:);
        for k = 1:numel(MUSCLES)
            X = cell2mat(D.emg_cycles.(MUSCLES{k})(:)') ./ mvc.(MUSCLES{k}) * 100;  % 1001 x strides
            avg{e}(:, k) = mean(X, 2, 'omitnan');
            sdv{e}(:, k) = std(X, 0, 2, 'omitnan');
        end
        ncyc(e) = size(X, 2);
    end
    [~, act_name] = fileparts(f_active);
    fprintf('%-12s strides: NoExo=%d  Inactive=%d  Active=%d  (active = %s)\n', ...
            tag, ncyc(1), ncyc(2), ncyc(3), act_name);

    % --- plot: 1 x 4 muscles ---
    fig = figure('Name', sprintf('%s - %s', SUBJECT, COND_LABELS{c}), 'Color', 'w', ...
                 'Units', 'centimeters', 'Position', [2 2+2*(c-1) 36 9]);
    h = gobjects(1, 3);
    for k = 1:numel(MUSCLES)
        ax = subplot(1, numel(MUSCLES), k); hold(ax, 'on');
        for e = 1:3
            m = avg{e}(:, k);  s = sdv{e}(:, k);
            fill(ax, [pgc; flipud(pgc)], [m - s; flipud(m + s)], COLORS{e}, ...
                 'FaceAlpha', 0.15, 'EdgeColor', 'none', 'HandleVisibility', 'off');
            h(e) = plot(ax, pgc, m, 'Color', COLORS{e}, 'LineWidth', 2.5);
        end
        xlim(ax, [0 100]);
        yl = ylim(ax); ylim(ax, [0 yl(2)]);
        set(ax, 'FontName', 'Times New Roman', 'FontSize', 12, 'Box', 'off');
        if SHOW_LABELS
            title(ax, MUSCLE_NAMES{k}, 'FontWeight', 'normal');
            xlabel(ax, 'Gait cycle (%)');
            if k == 1, ylabel(ax, 'Muscle activity (% MVC)'); end
        end
    end
    if SHOW_LABELS
        legend(h, EX_NAMES, 'Orientation', 'horizontal', 'Box', 'off', ...
               'Position', [0.35 0.005 0.3 0.05], 'FontName', 'Times New Roman');
        sgtitle(sprintf('%s  |  %s', SUBJECT, COND_LABELS{c}), 'FontName', 'Times New Roman');
    end

    if SAVE
        base = fullfile(out_dir, sprintf('%s_%s', SUBJECT, strrep(tag, '.', 'p')));
        savefig(fig, [base '.fig']);
        save_png(fig, [base '.png'], 600);
    end
end
fprintf('Done.\n');

%% ================= helper functions =================
function mvc = read_mvc(mfile, muscles)
    % Parse lines like "mvc.mvc_VL = 0.00010441;" from build_all_metrics.m
    txt = fileread(mfile);
    mvc = struct();
    for k = 1:numel(muscles)
        tok = regexp(txt, ['^\s*mvc\.mvc_' muscles{k} '\s*=\s*([-+0-9.eE]+)'], 'tokens', 'once', 'lineanchors');
        if isempty(tok), error('Could not find mvc.mvc_%s in %s', muscles{k}, mfile); end
        mvc.(muscles{k}) = str2double(tok{1});
    end
end

function f = active_trial_file(subj_dir, subject, tag)
    % Use the active trial recorded in the metrics file (same one used for the
    % paper statistics); fall back to active_rl_trial1 if unavailable.
    f = fullfile(subj_dir, sprintf('Processed_%s_active_rl_trial1.mat', tag));
    mfile = fullfile(subj_dir, sprintf('%s_%s_metrics.mat', subject, strrep(tag, '.', 'p')));
    if isfile(mfile)
        S = load(mfile, 'metrics');
        if isfield(S, 'metrics') && isfield(S.metrics, 'active_trial_used') ...
                && ~isempty(S.metrics.active_trial_used)
            cand = fullfile(subj_dir, char(S.metrics.active_trial_used));
            if isfile(cand), f = cand; end
        end
    end
end

function save_png(h, file, dpi)
    try
        exportgraphics(h, file, 'Resolution', dpi);
    catch
        set(h, 'Units', 'centimeters'); p = get(h, 'Position');
        set(h, 'PaperUnits', 'centimeters', 'PaperPositionMode', 'manual', ...
               'PaperSize', [p(3) p(4)], 'PaperPosition', [0 0 p(3) p(4)]);
        print(h, file, '-dpng', sprintf('-r%d', dpi));
    end
end
