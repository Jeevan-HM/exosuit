% analyze_all_subjects.m
clear; clc; close all;

% Setup paths and subjects
base_dir = fileparts(mfilename('fullpath'));
if isempty(base_dir)
    base_dir = pwd;
end
subjects = {'Amir', 'Jeevan', 'Mason', 'Ruthvik','Asha','Dez','Par','Rachitha'};
conditions = {'inc0spd0p8.mat', 'inc0spd1p2.mat', 'inc5spd0p8.mat', 'inc5spd1p2.mat'};
cond_names = {'Inc 0, Spd 0.8', 'Inc 0, Spd 1.2', 'Inc 5, Spd 0.8', 'Inc 5, Spd 1.2'};
colors = [0 0.4470 0.7410; 0.8500 0.3250 0.0980; 0.9290 0.6940 0.1250; 0.4940 0.1840 0.5560];

plot_subject = 'Mason'; % The one subject to plot trajectories for
use_95_ci = false; % Set to true for 95% CI shading, false for ±1 Standard Deviation shading
init_final_window = 3; % # of samples averaged at the start/end for init/final (robust to single-sample noise)

% --- Combined trajectory figure (Oct 2026) ---
COMBINED_TRAJ = true;   % true  -> ONE figure: (a) training cost | (b) EMG effort | (c) kinematic error A/C
                        % false -> three separate figures (original behaviour)
TRAJ_W_CM = 30; TRAJ_H_CM = 8;   % figure size (cm); 18 cm = full page width
TRAJ_FS   = 12;                    % font size
TRAJ_LW   = 2;                     % mean-line width
cond_long = {'0% grade, 0.8 m/s', '0% grade, 1.2 m/s', '10% grade, 0.8 m/s', '10% grade, 1.2 m/s'};
SAVE_TRAJ = true;                 % true -> save supp_figures/supp_training_P<ID>.png (600 dpi)
TRAJ_SUBJECTS  = {'all'};   % whose trajectories to plot: {plot_subject}, a list such as
                                   % {'Amir','Asha'}, or 'all' (every name in `subjects`, one figure each)
PLOT_GROUP_FIG = true;             % false -> skip the group initial-vs-final box-plot figure
                                   %          (statistics and the text report are still computed)
% Participant IDs used in the paper (S1-S8 / supplementary P1-P8; alphabetical order).
% Saved trajectory figures are named supp_training_P<ID>.png to match the LaTeX placeholders.
PID_NAMES = {'Amir','Asha','Dez','Jivan','Mason','Par','Rachitha','Ruthvik'};
PID_ALIAS = {'Jeevan','Jivan'};    % folder spelling -> name in PID_NAMES
SUPP_DIR  = fullfile(base_dir, 'supp_figures');   % where the supp_training_P<ID>.png files go

% --- Publication style (applies to all figures) ---
set(groot, 'defaultAxesFontName','Times New Roman', 'defaultTextFontName','Times New Roman', ...
           'defaultLegendFontName','Times New Roman', 'defaultAxesFontSize',13, ...
           'defaultAxesLineWidth',1.0);
cond_short = {'0% / 0.8', '0% / 1.2', '10% / 0.8', '10% / 1.2'}; % grade / speed (m/s)

%% Part 1: Plotting trajectories (one figure per subject in TRAJ_SUBJECTS)
if (ischar(TRAJ_SUBJECTS) || isstring(TRAJ_SUBJECTS) || (iscell(TRAJ_SUBJECTS) && numel(TRAJ_SUBJECTS)==1)) ...
        && strcmpi(char(string(TRAJ_SUBJECTS)), 'all')
    TRAJ_SUBJECTS = subjects;   % 'all' or {'all'}
end
if ischar(TRAJ_SUBJECTS), TRAJ_SUBJECTS = {TRAJ_SUBJECTS}; end
for ps = 1:numel(TRAJ_SUBJECTS)
    plot_subject = TRAJ_SUBJECTS{ps};
    if COMBINED_TRAJ
        fprintf('Plotting combined training trajectories for %s...\n', plot_subject);
        figT = figure('Name', sprintf('training_trajectories_%s', plot_subject), 'Color', 'w', ...
                      'Units', 'centimeters', 'Position', [2+0.6*(ps-1) 2+0.6*(ps-1) TRAJ_W_CM TRAJ_H_CM]);
        % layout (normalized units)
        Lm = 0.075; Rm = 0.01; gp = 0.075; gpK = 0.08; Bm = 0.34; Tm = 0.04;   % gpK: wider gap before (c)
        W = (1 - Lm - Rm - gp - gpK) / 3;  H = 1 - Bm - Tm;  kg = 0.07;  Hk = (H - kg) / 2;
        xK0 = Lm + 2*W + gp + gpK;                                % left edge of panel (c)
        posC  = [Lm,          Bm,           W, H];
        posE  = [Lm + W + gp, Bm,           W, H];
        posKA = [xK0,         Bm + Hk + kg, W, Hk];
        posKC = [xK0,         Bm,           W, Hk];
        axCost = axes(figT, 'Position', posC);  axEmg = axes(figT, 'Position', posE);
        axKA   = axes(figT, 'Position', posKA); axKC  = axes(figT, 'Position', posKC);
        allAx = [axCost axEmg axKA axKC];
        for a_ = allAx, hold(a_, 'on'); grid(a_, 'on'); end
        hC = gobjects(1, length(conditions));
        for c = 1:length(conditions)
            file_path = fullfile(base_dir, plot_subject, 'Final', conditions{c});
            if ~isfile(file_path), warning('File %s not found. Skipping.', file_path); continue; end
            data = load(file_path);
            hC(c) = plot_band(axCost, data.all_costs, colors(c, :), use_95_ci, TRAJ_LW);
            plot_band(axEmg, data.all_emgs,  colors(c, :), use_95_ci, TRAJ_LW);
            plot_band(axKA,  data.all_kineA, colors(c, :), use_95_ci, TRAJ_LW);
            plot_band(axKC,  data.all_kineC, colors(c, :), use_95_ci, TRAJ_LW);
        end
        set(allAx, 'FontName', 'Times New Roman', 'FontSize', TRAJ_FS - 1, 'Box', 'off', 'TickDir', 'out');
        ylabel(axCost, 'Training Cost', 'FontSize', TRAJ_FS);
        ylabel(axEmg,  'EMG Effort',    'FontSize', TRAJ_FS);
        ylabel(axKA, 'A', 'FontSize', TRAJ_FS); ylabel(axKC, 'C', 'FontSize', TRAJ_FS);

        % shared labels, arrow, and panel letters on an invisible full-figure axes
        axBG = axes(figT, 'Position', [0 0 1 1], 'Visible', 'off', 'HitTest', 'off');
        hold(axBG, 'on'); xlim(axBG, [0 1]); ylim(axBG, [0 1]);
        xK = posKA(1) - 0.055;                                   % 'Kinematic Error' well left of the A/C labels
        text(axBG, xK, Bm + H/2, 'Kinematic Error', 'Rotation', 90, 'HorizontalAlignment', 'center', ...
             'VerticalAlignment', 'middle', 'FontName', 'Times New Roman', 'FontSize', TRAJ_FS);
        yA = Bm - 0.12; hl = 0.012; hw = 0.022;                  % arrow + 'Gait Samples'
        plot(axBG, [Lm, 1 - Rm - hl], [yA yA], 'k-', 'LineWidth', 0.9);
        patch(axBG, [1 - Rm - hl, 1 - Rm - hl, 1 - Rm], [yA - hw, yA + hw, yA], 'k', 'EdgeColor', 'none');
        text(axBG, Lm + (1 - Lm - Rm)/2, yA, 'Gait Samples', 'HorizontalAlignment', 'center', ...
             'VerticalAlignment', 'middle', 'BackgroundColor', 'w', 'Margin', 2, ...
             'FontName', 'Times New Roman', 'FontSize', TRAJ_FS);
        pl = {'(a)', '(b)', '(c)'}; px = [posC(1) + W/2, posE(1) + W/2, posKA(1) + W/2];
        for i = 1:3
            text(axBG, px(i), Bm - 0.22, pl{i}, 'HorizontalAlignment', 'center', ...
                 'FontName', 'Times New Roman', 'FontSize', TRAJ_FS);
        end
        ok = isgraphics(hC);
        lg = legend(axCost, hC(ok), cond_long(ok), 'Orientation', 'horizontal', 'Box', 'off', ...
                    'FontName', 'Times New Roman', 'FontSize', TRAJ_FS);
        set(lg, 'Units', 'normalized', 'Location', 'none'); drawnow;
        lp = get(lg, 'Position');                                % natural size of the legend
        set(lg, 'Position', [0.5 - lp(3)/2, 0.005, lp(3), lp(4)]);   % centred under the figure
        % re-apply positions (legend creation must not move the panels)
        set(axCost, 'Position', posC); set(axEmg, 'Position', posE);
        set(axKA, 'Position', posKA);  set(axKC, 'Position', posKC);
        if SAVE_TRAJ
            if ~exist(SUPP_DIR, 'dir'), mkdir(SUPP_DIR); end
            nm = plot_subject; ia = find(strcmpi(PID_ALIAS(:,1), nm)); if ~isempty(ia), nm = PID_ALIAS{ia,2}; end
            pid = find(strcmpi(PID_NAMES, nm));
            if isempty(pid), fname = sprintf('supp_training_%s.png', plot_subject);
            else,            fname = sprintf('supp_training_P%d.png', pid); end
            save_png(figT, fullfile(SUPP_DIR, fname), 600);
            fprintf('  saved %s  (%s)\n', fname, plot_subject);
        end
    else
        fprintf('Plotting detailed trajectories for %s...\n', plot_subject);

        fig_cost = figure('Name', 'Training Cost', 'Position', [100, 100, 800, 600], 'Color', 'w'); hold on; grid on;
        title(sprintf('Training Cost for %s', plot_subject)); xlabel('Samples'); ylabel('Cost');

        fig_emg = figure('Name', 'EMG Activity', 'Position', [150, 150, 800, 600], 'Color', 'w'); hold on; grid on;
        title(sprintf('EMG Activity for %s', plot_subject)); xlabel('Samples'); ylabel('EMG');

        fig_kine = figure('Name', 'Kinematics', 'Position', [200, 200, 800, 800], 'Color', 'w');
        ax_kineA = subplot(2, 1, 1); hold on; grid on; %title(sprintf('Kinematic A Error for %s', plot_subject)); ylabel('Kine A');
        ax_kineC = subplot(2, 1, 2); hold on; grid on; %title(sprintf('Kinematic C Error for %s', plot_subject)); ylabel('Kine C'); xlabel('Samples');

        cost_lines = gobjects(1, length(conditions));
        emg_lines = gobjects(1, length(conditions));
        kineA_lines = gobjects(1, length(conditions));
        kineC_lines = gobjects(1, length(conditions));

        for c = 1:length(conditions)
            file_path = fullfile(base_dir, plot_subject, 'Final', conditions{c});
            if ~isfile(file_path)
                warning('File %s not found. Skipping.', file_path);
                continue;
            end
            data = load(file_path);
    
            figure(fig_cost);
            cost_lines(c) = plot_mean_ci(gca, data.all_costs, colors(c, :), use_95_ci);
    
            figure(fig_emg);
            emg_lines(c) = plot_mean_ci(gca, data.all_emgs, colors(c, :), use_95_ci);
    
            axes(ax_kineA);
            kineA_lines(c) = plot_mean_ci(gca, data.all_kineA, colors(c, :), use_95_ci);
    
            axes(ax_kineC);
            kineC_lines(c) = plot_mean_ci(gca, data.all_kineC, colors(c, :), use_95_ci);
        end

        figure(fig_cost); legend(cost_lines(isgraphics(cost_lines)), cond_names(isgraphics(cost_lines)), 'Location', 'best');
        figure(fig_emg); legend(emg_lines(isgraphics(emg_lines)), cond_names(isgraphics(emg_lines)), 'Location', 'best');
        axes(ax_kineA); legend(kineA_lines(isgraphics(kineA_lines)), cond_names(isgraphics(kineA_lines)), 'Location', 'best');
        axes(ax_kineC); legend(kineC_lines(isgraphics(kineC_lines)), cond_names(isgraphics(kineC_lines)), 'Location', 'best');
    end
end

%% Part 2: Calculate reductions for ALL subjects
fprintf('\nCalculating average reductions across all subjects...\n');

% Initialize storage for Initial and Final values
init_costs = zeros(length(subjects), length(conditions));
final_costs = zeros(length(subjects), length(conditions));

init_emgs = zeros(length(subjects), length(conditions));
final_emgs = zeros(length(subjects), length(conditions));

init_kineA = zeros(length(subjects), length(conditions));
final_kineA = zeros(length(subjects), length(conditions));

init_kineC = zeros(length(subjects), length(conditions));
final_kineC = zeros(length(subjects), length(conditions));

for s = 1:length(subjects)
    subj = subjects{s};
    for c = 1:length(conditions)
        file_path = fullfile(base_dir, subj, 'Final', conditions{c});
        if ~isfile(file_path)
            init_costs(s,c)=NaN; final_costs(s,c)=NaN;
            init_emgs(s,c)=NaN; final_emgs(s,c)=NaN;
            init_kineA(s,c)=NaN; final_kineA(s,c)=NaN;
            init_kineC(s,c)=NaN; final_kineC(s,c)=NaN;
            continue;
        end
        data = load(file_path);
        
        % Cost/EMG are non-negative efforts -> average the rollouts directly.
        % KineA/KineC are SIGNED errors -> use per-sample MAGNITUDE so positive and
        % negative errors don't cancel (otherwise "error" collapses toward zero).
        [init_costs(s, c), final_costs(s, c)] = get_init_final(data.all_costs, init_final_window, false);
        [init_emgs(s, c),  final_emgs(s, c)]  = get_init_final(data.all_emgs,  init_final_window, false);
        [init_kineA(s, c), final_kineA(s, c)] = get_init_final(data.all_kineA, init_final_window, true);
        [init_kineC(s, c), final_kineC(s, c)] = get_init_final(data.all_kineC, init_final_window, true);
    end
end

% Mean and Std of Initial and Final values across subjects
m_init_costs = mean(init_costs, 1, 'omitnan');  s_init_costs = std(init_costs, 0, 1, 'omitnan');
m_fin_costs = mean(final_costs, 1, 'omitnan');  s_fin_costs = std(final_costs, 0, 1, 'omitnan');

m_init_emgs = mean(init_emgs, 1, 'omitnan');    s_init_emgs = std(init_emgs, 0, 1, 'omitnan');
m_fin_emgs = mean(final_emgs, 1, 'omitnan');    s_fin_emgs = std(final_emgs, 0, 1, 'omitnan');

m_init_kineA = mean(init_kineA, 1, 'omitnan');  s_init_kineA = std(init_kineA, 0, 1, 'omitnan');
m_fin_kineA = mean(final_kineA, 1, 'omitnan');  s_fin_kineA = std(final_kineA, 0, 1, 'omitnan');

m_init_kineC = mean(init_kineC, 1, 'omitnan');  s_init_kineC = std(init_kineC, 0, 1, 'omitnan');
m_fin_kineC = mean(final_kineC, 1, 'omitnan');  s_fin_kineC = std(final_kineC, 0, 1, 'omitnan');

% Compute Percentage Reductions based on the MAGNITUDE of the overall means
% This ensures the text exactly matches the visual difference between the bars
mean_pct_red_costs = (abs(m_init_costs) - abs(m_fin_costs)) ./ abs(m_init_costs) * 100;
mean_pct_red_emgs = (abs(m_init_emgs) - abs(m_fin_emgs)) ./ abs(m_init_emgs) * 100;
mean_pct_red_kineA = (abs(m_init_kineA) - abs(m_fin_kineA)) ./ abs(m_init_kineA) * 100;
mean_pct_red_kineC = (abs(m_init_kineC) - abs(m_fin_kineC)) ./ abs(m_init_kineC) * 100;

%% Part 2b: STATISTICS (initial vs final, paired across participants)
% Same approach as the muscle-activity analysis: per participant we take the
% initial->final change, then test it with the paired non-parametric Wilcoxon
% signed-rank test across the N participants (small N, no normality assumption).
% Per condition -> FDR across the 4 conditions (for the figure stars); pooled
% over conditions -> one headline test per metric, FDR across the 4 metrics.
hasStats = (exist('signrank','file') == 2) || license('test','Statistics_Toolbox');
metric_init = {init_costs, init_emgs, init_kineA, init_kineC};
metric_fin  = {final_costs, final_emgs, final_kineA, final_kineC};
metric_lab  = {'Training cost','EMG effort','Kinematic A error','Kinematic C error'};
nMet = 4; nCond = length(conditions);

p_cond = nan(nMet, nCond); q_cond = nan(nMet, nCond);
p_pool = nan(1, nMet); dz_pool = nan(1, nMet); red_pool = nan(1, nMet);
for mi = 1:nMet
    I = metric_init{mi}; F = metric_fin{mi};
    for c = 1:nCond                                   % per condition
        r = (I(:,c) - F(:,c)) ./ I(:,c) * 100; r = r(isfinite(r));
        p_cond(mi,c) = signrank_safe(r, hasStats);
    end
    q_cond(mi,:) = bh_fdr(p_cond(mi,:));              % FDR across the 4 conditions
    Ip = mean(I,2,'omitnan'); Fp = mean(F,2,'omitnan');   % pooled over conditions
    rp = (Ip - Fp) ./ Ip * 100; rp = rp(isfinite(rp));
    red_pool(mi) = mean(rp); dz_pool(mi) = effect_dz(rp); p_pool(mi) = signrank_safe(rp, hasStats);
end
q_pool = bh_fdr(p_pool);                              % FDR across the 4 metrics

%% Part 3: Plot Initial vs Final with Percentage Reduction
if PLOT_GROUP_FIG
    figure('Name', 'group_training_initial_vs_final', 'Color', 'w', ...
        'Units', 'centimeters', 'Position', [2, 2, 18, 16]);   % ~double-column width

    plot_grouped_box(subplot(2, 2, 1), init_costs,  final_costs,  mean_pct_red_costs,  cond_short, 'Training cost (a.u.)',    true,  q_cond(1,:));
    plot_grouped_box(subplot(2, 2, 2), init_emgs,   final_emgs,   mean_pct_red_emgs,   cond_short, 'EMG effort (norm.)',      false, q_cond(2,:));
    plot_grouped_box(subplot(2, 2, 3), init_kineA,  final_kineA,  mean_pct_red_kineA,  cond_short, 'Kinematic A error (rad)', false, q_cond(3,:));
    plot_grouped_box(subplot(2, 2, 4), init_kineC,  final_kineC,  mean_pct_red_kineC,  cond_short, 'Kinematic C error (rad)', false, q_cond(4,:));

    % Export the overall figure as a high-resolution PNG
    save_png(gcf, fullfile(base_dir, 'group_training_initial_vs_final.png'), 600);
end

fprintf('\nAnalysis complete! Figures have been generated.\n');

%% Part 4: Copy-pasteable results report (for writing the paper)
metric_names = {'Training cost (a.u.)', 'EMG effort (norm.)', ...
                'Kinematic A error (rad, stance peak-flexion)', ...
                'Kinematic C error (rad, swing peak-flexion)'};
inits = {init_costs, init_emgs, init_kineA, init_kineC};
fins  = {final_costs, final_emgs, final_kineA, final_kineC};
cond_plain = {'grade 0%, 0.8', 'grade 0%, 1.2', 'grade 10%, 0.8', 'grade 10%, 1.2'};

R = sprintf('\n>>> COPY FROM HERE - ONLINE TRAINING REPORT >>>\n');
R = [R sprintf('N = %d participants; 4 walking conditions (grade 0%%/10%% x speed 0.8/1.2 m/s).\n', numel(subjects))];
R = [R sprintf('Init/Final = mean of the first/last %d training samples (across the 2 rollouts).\n', init_final_window)];
R = [R sprintf('Kinematic errors use per-sample MAGNITUDE (RMS) so signed errors do not cancel.\n')];
R = [R sprintf('Reduction%% = (Init-Final)/Init*100 on group means (positive = improvement).\n')];
R = [R sprintf('Stats: Wilcoxon signed-rank (Init vs Final) across participants; per-condition p\n')];
R = [R sprintf('       (q = FDR across the 4 conditions), plus a pooled test per metric (q across metrics).\n\n')];
for mi = 1:4
    I = inits{mi}; F = fins{mi};
    mI = mean(I,1,'omitnan'); sI = std(I,0,1,'omitnan');
    mF = mean(F,1,'omitnan'); sF = std(F,0,1,'omitnan');
    red = (mI - mF) ./ mI * 100;
    R = [R sprintf('[%s]\n', metric_names{mi})];
    R = [R sprintf('  %-16s %16s %16s %8s %7s %7s\n', 'Condition', 'Init(mean+/-SD)', 'Final(mean+/-SD)', 'Red%', 'p', 'q')];
    for c = 1:numel(conditions)
        R = [R sprintf('  %-16s %7.3f+/-%-6.3f %7.3f+/-%-6.3f %7.1f %7.3f %7.3f %s\n', ...
            cond_plain{c}, mI(c), sI(c), mF(c), sF(c), red(c), p_cond(mi,c), q_cond(mi,c), sig_label(q_cond(mi,c),0.05))];
    end
    R = [R sprintf('  POOLED over conditions: %.1f%% reduction, dz=%.2f, p=%.3f, q=%.3f  %s\n\n', ...
        red_pool(mi), dz_pool(mi), p_pool(mi), q_pool(mi), sig_label(q_pool(mi),0.05))];
end
R = [R sprintf('<<< COPY TO HERE <<<\n')];
fprintf('%s', R);
fid = fopen(fullfile(base_dir, 'training_report.txt'), 'w');
if fid > 0, fprintf(fid, '%s', R); fclose(fid); fprintf('Report also saved to training_report.txt\n'); end

%% Helper Functions

function p = signrank_safe(x, hasStats)
    x = x(~isnan(x));
    if hasStats && numel(x) >= 2, p = signrank(x); else, p = NaN; end
end

function q = bh_fdr(p)
    p = p(:)'; m = numel(p); q = nan(1,m); ok = ~isnan(p); pp = p(ok); mm = numel(pp);
    if mm == 0, return; end
    [ps, ix] = sort(pp); qs = ps .* mm ./ (1:mm);
    for i = mm-1:-1:1, qs(i) = min(qs(i), qs(i+1)); end
    qv = nan(1,mm); qv(ix) = min(qs,1); q(ok) = qv;
end

function dz = effect_dz(x)
    x = x(~isnan(x));
    if numel(x) < 2 || std(x) == 0, dz = NaN; else, dz = mean(x)/std(x); end
end

function s = stars(q)
    if isnan(q), s = ''; elseif q < 0.001, s = '***';
    elseif q < 0.01, s = '**'; elseif q < 0.05, s = '*'; else, s = ''; end
end

function s = sig_label(q, alpha)
    if isnan(q), s = 'n/a'; elseif q < 0.001, s = '*** sig';
    elseif q < 0.01, s = '**  sig'; elseif q < alpha, s = '*   sig'; else, s = 'n.s.'; end
end

function save_png(h, file, dpi)
    % High-resolution PNG export. exportgraphics accepts a figure only in
    % R2020b+, so fall back to print() (works with a figure in every version).
    try
        exportgraphics(h, file, 'Resolution', dpi);
    catch
        set(h, 'Units', 'centimeters'); p = get(h, 'Position');
        set(h, 'PaperUnits', 'centimeters', 'PaperPositionMode', 'manual', ...
            'PaperSize', [p(3) p(4)], 'PaperPosition', [0 0 p(3) p(4)]);
        print(h, file, '-dpng', sprintf('-r%d', dpi));
    end
end

function p = plot_band(ax, data, color, use_95_ci, lw)
    % Mean across rollouts with a shaded +/-1 SD (or 95% CI) band, drawn on ax only
    % (no figure-wide side effects, unlike plot_mean_ci).
    mean_val = mean(data, 2, 'omitnan');  n = sum(~isnan(data), 2);
    sd = std(data, 0, 2, 'omitnan');
    if use_95_ci, sh = 1.96 * sd ./ sqrt(n); else, sh = sd; end
    sh(isnan(sh) | isinf(sh)) = 0;
    x = find(~isnan(mean_val));
    if isempty(x), p = plot(ax, NaN, NaN, 'Color', color); return; end
    m = mean_val(x); sh = sh(x);
    fill(ax, [x; flipud(x)], [m + sh; flipud(m - sh)], color, 'EdgeColor', 'none', ...
         'FaceAlpha', 0.12, 'HandleVisibility', 'off');
    p = plot(ax, x, m, 'Color', color, 'LineWidth', lw);
    xlim(ax, [min(x) max(x)]);
end

function p = plot_mean_ci(ax, data, color, use_95_ci)
    % Calculate sample mean and valid N
    mean_val = mean(data, 2, 'omitnan');
    n_samples = sum(~isnan(data), 2);
    
    % Standard Deviation across rollouts (per sample). NOTE: previously divided
    % by 2 with no statistical basis, which halved every band/CI. Removed.
    std_val = std(data, 0, 2, 'omitnan');
    
    if use_95_ci
        % Standard Error of the Mean (SEM)
        sem = std_val ./ sqrt(n_samples);
        % 95% CI uses 1.96 multiplier (Large-sample Normal approximation).
        shade_val = 1.96 * sem; 
    else
        % Use Standard Deviation
        shade_val = std_val;
    end
    
    shade_val(isnan(shade_val) | isinf(shade_val)) = 0; % Prevent NaN/Inf issues
    
    valid_idx = find(~isnan(mean_val));
    if isempty(valid_idx)
        p = plot(ax, NaN, NaN, 'Color', color);
        return;
    end
    x = valid_idx;
    mean_val = mean_val(valid_idx);
    shade_val = shade_val(valid_idx);
    
    % Fill for shaded region with semi-transparency
    fill(ax, [x', fliplr(x')], ...
         [mean_val' + shade_val', fliplr(mean_val' - shade_val')], ...
         color, 'EdgeColor', 'none', 'FaceAlpha', 0.1);
    % Plot mean
    p = plot(ax, x, mean_val, 'Color', color, 'LineWidth', 5);
    xlim(ax, [min(x) max(x)]);
    set(gcf, 'Color', 'w');
    fontsize(12,"points")
end

function [init_val, final_val] = get_init_final(data, win, use_magnitude)
    % Collapse the rollout columns to one value per sample, then average the first
    % and last `win` valid samples (robust to single-sample noise).
    if nargin < 2 || isempty(win), win = 1; end
    if nargin < 3, use_magnitude = false; end

    if use_magnitude
        % per-sample error MAGNITUDE across rollouts (RMS) -> no sign cancellation
        per_sample = sqrt(mean(data.^2, 2, 'omitnan'));
    else
        per_sample = mean(data, 2, 'omitnan');
    end

    valid_idx = find(~isnan(per_sample));
    if isempty(valid_idx)
        init_val = NaN; final_val = NaN; return;
    end
    v = per_sample(valid_idx);
    w = min(win, numel(v));
    init_val  = mean(v(1:w));
    final_val = mean(v(end-w+1:end));
end

function plot_grouped_box(ax, data_init, data_final, mean_pct_red, cond_labels, ylabel_str, show_legend, q_vec)
    axes(ax); hold on; grid on;
    if nargin < 8, q_vec = nan(1, numel(mean_pct_red)); end
    
    [n_subj, n_cond] = size(data_init);
    
    % --- Spacing Parameters (Manually Adjustable) ---
    box_width = 0.3;           % Width of each individual box
    intra_group_spacing = 0.4; % Distance between Initial and Final centers
    inter_group_spacing = 1.6; % Distance between start of one group and the next
    
    % Prepare data for boxchart
    y_init_flat = data_init(:);
    y_final_flat = data_final(:);
    
    % X centers for Initial boxes
    x_init_centers = (0:n_cond-1) * inter_group_spacing + 1;
    % X centers for Final boxes
    x_final_centers = x_init_centers + intra_group_spacing;
    
    x_init_flat = repmat(x_init_centers, n_subj, 1);
    x_init_flat = x_init_flat(:);
    
    x_final_flat = repmat(x_final_centers, n_subj, 1);
    x_final_flat = x_final_flat(:);
    
    % Create individual box charts (outlier markers hidden; box + whiskers show spread)
    b1 = boxchart(x_init_flat, y_init_flat, 'BoxFaceColor', [0.2 0.6 0.8], 'BoxWidth', box_width, 'LineWidth', 1.2, 'MarkerStyle', 'none');
    b2 = boxchart(x_final_flat, y_final_flat, 'BoxFaceColor', [0.8 0.4 0.2], 'BoxWidth', box_width, 'LineWidth', 1.2, 'MarkerStyle', 'none');

    % --- Publication formatting ---
    set(gca, 'XTick', (x_init_centers + x_final_centers) / 2, 'XTickLabel', cond_labels, ...
        'XTickLabelRotation', 0);                 % flat (horizontal) x labels
    ylabel(ylabel_str);
    xlabel('Grade (%) / speed (m/s)');
    if show_legend
        % legend ABOVE the axes so it never overlaps the reduction annotations
        legend([b1, b2], {'Initial', 'Final'}, 'Orientation', 'horizontal', ...
            'Location', 'northoutside', 'Box', 'off');
    end
    
    % Add percentage reduction annotations above the boxes
    for i = 1:length(mean_pct_red)
        if isnan(mean_pct_red(i)) || isinf(mean_pct_red(i))
            continue;
        end
        
        % Place text above the highest data point for this condition
        cond_data = [data_init(:, i); data_final(:, i)];
        max_val = max(cond_data, [], 'omitnan');
        
        if isempty(max_val) || isnan(max_val)
            continue;
        end
        
        % Ensure text stays above even if values are negative
        if max_val > 0
            y_text = max_val + 0.15 * abs(max_val);
        else
            y_text = max_val + 0.15 * abs(max_val); % less negative, so visually above
        end
        
        if y_text == 0
            y_text = 0.1;
        end
        
        % Arrow down for reduction, Arrow up for increase
        if mean_pct_red(i) >= 0
            txt = sprintf('%.1f%% \\downarrow', mean_pct_red(i));
            color = [0 0.5 0]; % Dark Green
        else
            txt = sprintf('+%.1f%% \\uparrow', abs(mean_pct_red(i)));
            color = [0.8 0 0]; % Red
        end

        % Append FDR significance stars (Wilcoxon initial vs final, this condition)
        s = stars(q_vec(i));
        if ~isempty(s), txt = [txt ' ' s]; end

        % Center text between Initial and Final boxes
        x_text = (x_init_centers(i) + x_final_centers(i)) / 2;

        text(x_text, y_text, txt, 'HorizontalAlignment', 'center', ...
            'FontWeight', 'bold', 'FontSize', 10, 'Color', color);
    end
    
    % Robust Y-axis limit adjustment
    y_data_all = [y_init_flat; y_final_flat];
    max_val_overall = max(y_data_all, [], 'omitnan');
    min_val_overall = min(y_data_all, [], 'omitnan');
    
    y_upper = max_val_overall + 0.3 * abs(max_val_overall) + 0.1;
    y_lower = min(min_val_overall, 0); 
    if y_lower < 0
        y_lower = y_lower - 0.15 * abs(y_lower) - 0.1;
    end
    
    % Adjust X-axis limit to neatly contain all boxes
    xlim([min(x_init_centers) - 0.5, max(x_final_centers) + 0.5]);

    set(gcf, 'Color', 'w');
    box off;
    ylim([y_lower, y_upper]);
end
