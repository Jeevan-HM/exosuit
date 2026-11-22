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
SUBJECT     = 'Ruthvik'; % e.g. 'Amir'. Leave '' to choose from a list.
COND_IDX    = [1 2 3 4];     % which walking conditions to plot (1..4, see COND_TAGS below)
                         %   [1 2] = level walking only; [1 2 3 4] = all four
REMOVE_OUTLIERS   = true;  % drop outlier strides per muscle (visualization only)
DROP_FIRST_SAMPLE = true;  % drop sample at 0% GC (envelope starts at 0)
SAVE        = false;     % true -> save .fig and .png for each condition
SHOW_LABELS = true;      % axis labels / titles / legend on or off
COMBINED    = true;      % true  -> ONE figure: rows = walking conditions, columns = muscles
                         % false -> one figure per walking condition (original behaviour)
FIG_W_CM    = 18;        % combined figure size (cm); ~18 cm = full page width
FIG_H_CM    = 20;
FONT_SIZE   = 12;        % combined figure font size
SAME_Y_PER_MUSCLE = false;   % true -> all conditions share one y-range per muscle column
SHOW_ARROWS = true;      % arrows along the shared x/y labels (as in the reference figure)

% Walking conditions: file tag -> label used on the figure
COND_TAGS   = {'inc0_spd0.8', 'inc0_spd1.2', 'inc5_spd0.8', 'inc5_spd1.2'};
COND_LABELS = {'0% grade, 0.8 m/s', '0% grade, 1.2 m/s', ...
               '10% grade, 0.8 m/s', '10% grade, 1.2 m/s'};
COND_SHORT  = {'0%, 0.8 m/s', '0%, 1.2 m/s', '10%, 0.8 m/s', '10%, 1.2 m/s'};   % row labels (combined figure)

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

STORE = struct('c', {}, 'pgc', {}, 'avg', {}, 'sdv', {});   % used when COMBINED = true
for c = COND_IDX
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
    avg = cell(1, 3);  sdv = cell(1, 3);  nkept = zeros(3, numel(MUSCLES));  ntot = zeros(1, 3);
    for e = 1:3
        D = load(files{e}, 'emg_cycles', 'pgc_emg', 'n_cycles');
        pgc = D.pgc_emg(:);
        if DROP_FIRST_SAMPLE, pgc = pgc(2:end); end
        for k = 1:numel(MUSCLES)
            X = cell2mat(D.emg_cycles.(MUSCLES{k})(:)') ./ mvc.(MUSCLES{k}) * 100;  % 1001 x strides
            if DROP_FIRST_SAMPLE, X = X(2:end, :); end
            keep = true(1, size(X, 2));
            if REMOVE_OUTLIERS, keep = outlier_strides(X); end
            avg{e}(:, k) = mean(X(:, keep), 2, 'omitnan');
            sdv{e}(:, k) = std(X(:, keep), 0, 2, 'omitnan');
            nkept(e, k)  = sum(keep);
        end
        ntot(e) = size(X, 2);
    end
    [~, act_name] = fileparts(f_active);
    fprintf('%-12s strides kept (min over muscles / total): NoExo=%d/%d  Inactive=%d/%d  Active=%d/%d  (active = %s)\n', ...
            tag, min(nkept(1,:)), ntot(1), min(nkept(2,:)), ntot(2), min(nkept(3,:)), ntot(3), act_name);

    if COMBINED   % keep the data; the single combined figure is drawn after the loop
        STORE(end+1) = struct('c', c, 'pgc', pgc, 'avg', {avg}, 'sdv', {sdv}); %#ok<SAGROW>
        continue;
    end

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
%% ===== COMBINED FIGURE: rows = walking conditions, columns = muscles =====
if COMBINED && ~isempty(STORE)
    nR = numel(STORE); nC = numel(MUSCLES); fs = FONT_SIZE;
    fig = figure('Name', sprintf('%s - all conditions', SUBJECT), 'Color', 'w', ...
                 'Units', 'centimeters', 'Position', [2 2 FIG_W_CM FIG_H_CM]);
    % layout (normalized units): margins leave room for the shared labels
    Lm = 0.10; Rm = 0.07; Bm = 0.13; Tm = 0.05; hg = 0.035; vg = 0.04;
    w = (1 - Lm - Rm - (nC-1)*hg) / nC;
    h = (1 - Bm - Tm - (nR-1)*vg) / nR;
    axAll = gobjects(nR, nC); hL = gobjects(1, 3);
    for r = 1:nR
        pgc = STORE(r).pgc; avg = STORE(r).avg; sdv = STORE(r).sdv;
        for k = 1:nC
            pos = [Lm + (k-1)*(w + hg), 1 - Tm - r*h - (r-1)*vg, w, h];
            ax = axes(fig, 'Position', pos); hold(ax, 'on'); axAll(r, k) = ax;
            for e = 1:3
                m = avg{e}(:, k);  sd = sdv{e}(:, k);
                fill(ax, [pgc; flipud(pgc)], [m - sd; flipud(m + sd)], COLORS{e}, ...
                     'FaceAlpha', 0.15, 'EdgeColor', 'none', 'HandleVisibility', 'off');
                hp = plot(ax, pgc, m, 'Color', COLORS{e}, 'LineWidth', 1.8);
                if r == 1 && k == 1, hL(e) = hp; end
            end
            xlim(ax, [0 100]); yl = ylim(ax); ylim(ax, [0 yl(2)]);
            set(ax, 'XTick', [0 50 100], 'FontName', 'Times New Roman', 'FontSize', fs - 1, ...
                    'Box', 'off', 'TickDir', 'out', 'TickLength', [0.02 0.02]);
            if SHOW_LABELS && r == 1
                title(ax, MUSCLE_NAMES{k}, 'FontWeight', 'normal', 'FontSize', fs);
            end
            if SHOW_LABELS && k == nC   % row label on the right, reading bottom-to-top
                text(ax, 1.06, 0.5, COND_SHORT{STORE(r).c}, 'Units', 'normalized', 'Rotation', 90, ...
                     'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
                     'FontName', 'Times New Roman', 'FontSize', fs);
            end
        end
    end
    if SAME_Y_PER_MUSCLE
        for k = 1:nC
            yt = max(arrayfun(@(a) a.YLim(2), axAll(:, k)));
            set(axAll(:, k), 'YLim', [0 yt]);
        end
    end

    if SHOW_LABELS
        % shared axis labels on an invisible full-figure axes
        axBG = axes(fig, 'Position', [0 0 1 1], 'Visible', 'off', 'HitTest', 'off');
        hold(axBG, 'on'); xlim(axBG, [0 1]); ylim(axBG, [0 1]);
        yMid = Bm + (1 - Bm - Tm)/2;  xMid = Lm + (1 - Lm - Rm)/2;
        xY = 0.03; yX = Bm - 0.065;      % positions of the shared y- and x-labels
        if SHOW_ARROWS   % arrow lines drawn first, labels (white background) sit on top
            hl = 0.018; hw = 0.007;       % arrowhead length / half-width (normalized)
            plot(axBG, [xY xY], [Bm 1 - Tm - hl], 'k-', 'LineWidth', 0.8);
            patch(axBG, [xY - hw, xY + hw, xY], [1 - Tm - hl, 1 - Tm - hl, 1 - Tm], 'k', 'EdgeColor', 'none');
            plot(axBG, [Lm 1 - Rm - hl], [yX yX], 'k-', 'LineWidth', 0.8);
            patch(axBG, [1 - Rm - hl, 1 - Rm - hl, 1 - Rm], [yX - hw, yX + hw, yX], 'k', 'EdgeColor', 'none');
        end
        text(axBG, xY, yMid, 'Normalized Muscle Activity to MVC (%)', 'Rotation', 90, ...
             'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', 'BackgroundColor', 'w', ...
             'Margin', 2, 'FontName', 'Times New Roman', 'FontSize', fs);
        text(axBG, xMid, yX, 'Percent Gait Cycle', 'HorizontalAlignment', 'center', ...
             'VerticalAlignment', 'middle', 'BackgroundColor', 'w', 'Margin', 2, ...
             'FontName', 'Times New Roman', 'FontSize', fs);
        legend(axAll(1, 1), hL, EX_NAMES, 'Orientation', 'horizontal', 'Box', 'off', ...
               'FontName', 'Times New Roman', 'FontSize', fs, 'Units', 'normalized', ...
               'Position', [Lm, 0.005, 1 - Lm - Rm, 0.04]);
        for r = 1:nR, for k = 1:nC   % legend creation must not move the panels
            set(axAll(r, k), 'Position', [Lm + (k-1)*(w + hg), 1 - Tm - r*h - (r-1)*vg, w, h]);
        end, end
    end

    if SAVE
        % name matches the LaTeX placeholders: supp_muscle_P<ID>.png (P1-P8, alphabetical)
        PID_NAMES = {'Amir','Asha','Dez','Jivan','Mason','Par','Rachitha','Ruthvik'};
        nm = SUBJECT; if strcmpi(nm, 'Jeevan'), nm = 'Jivan'; end
        pid = find(strcmpi(PID_NAMES, nm));
        if isempty(pid), fname = sprintf('supp_muscle_%s', SUBJECT); else, fname = sprintf('supp_muscle_P%d', pid); end
        base = fullfile(out_dir, fname);
        savefig(fig, [base '.fig']);
        save_png(fig, [base '.png'], 600);
        fprintf('Saved %s.png (%s)\n', fname, SUBJECT);
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

function keep = outlier_strides(X)
    % Tukey rule on each stride's RMS deviation from the median waveform:
    % a stride is an outlier if its deviation > Q3 + 1.5*IQR.
    med  = median(X, 2, 'omitnan');
    dev  = sqrt(mean((X - med).^2, 1, 'omitnan'));
    s    = sort(dev(~isnan(dev)));  n = numel(s);
    qf   = @(p) interp1(linspace(0, 100, n), s, p);   % linear-interpolated percentile
    if n < 4, keep = true(size(dev)); return; end
    q1 = qf(25);  q3 = qf(75);
    keep = dev <= q3 + 1.5 * (q3 - q1);
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
