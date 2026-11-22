 %% aggregate_metrics.m
% Group-level analysis + paper figures from the per-comparison metric files
% produced by compare_trials.m (one `metrics` struct per subject x speed x
% incline, saved as *_metrics.mat, in canonical condition order
% {noexo, exoinactive, exoactive} x {VL, RF, BF, ST}).
%
% DESIGN (see header notes):
%   - Unit of analysis = SUBJECT. Each metrics file already holds one scalar
%     per stride-averaged cell, so here we only ever average ACROSS subjects.
%   - Primary DV = "support zone": extensors (VL,RF) in the extension phase,
%     flexors (BF,ST) in the flexion phase. Whole-cycle mean is supplementary.
%   - Framing = % reduction vs No-Exo, for Exo-Active and Exo-Inactive.
%   - Error bars = between-subject 95% CI. Significance = Wilcoxon signed-rank
%     (primary, small-N robust) + linear mixed model (generalization across
%     speed/incline/subjects), FDR-corrected across the 4 muscles.
%
% Missing subjects are fine: the script uses whatever *_metrics.mat it finds
% and reports how many subjects were included.

clear; clc; close all;

muscles   = {'VL', 'RF', 'BF', 'ST'};
is_ext_m  = [true true false false];   % VL,RF extensors ; BF,ST flexors
cond_list = {'noexo', 'exoinactive', 'exoactive'};

% >>> INDIVIDUAL CHECK <<< set true to also plot ONE participant's own metrics
% (their support-zone activity + reduction, with stride-to-stride SD). Group
% analysis always runs regardless of this flag.
plot_individual    = true;
individual_subject = 'Jivan';    % must match metrics.subject

% >>> FIGURE STYLE <<< tuned for a two-column journal. Edit these to taste;
% figures are drawn at a fixed physical size (cm) so exported fonts stay legible
% at column width. All text is set to Times New Roman.
FIG.font     = 'Times New Roman';
FIG.fontSize = 13;      % base font (pt). Readable at column width without dominating.
FIG.lineW    = 2.0;     % data line / marker edge width
FIG.axLineW  = 1.0;     % axis box width
FIG.markerSz = 55;      % individual-subject dot area
FIG.figW1col = 9.0;     % single-column figure width  (cm)  ~ journal column
FIG.figW2col = 18.0;    % double-column figure width  (cm)
FIG.figH1    = 7.5;     % height, single-row figures   (cm)
FIG.figH2    = 13.0;    % height, 2x2 figures          (cm)
FIG.cNoexo    = [0.35 0.35 0.35];
FIG.cInactive = [0.60 0.60 0.60];
FIG.cActive   = [0.15 0.53 0.82];
FIG.save = false;             % true -> auto-export each paper figure to FIG.dir
FIG.dir  = 'paper_figures';   % output subfolder (created under this script's folder)
FIG.fmt  = 'png';             % 'pdf' = vector (sharpest, best for LaTeX) | 'png' = raster
FIG.dpi  = 600;               % raster resolution when FIG.fmt = 'png'
set(groot, 'defaultAxesFontName', FIG.font, 'defaultTextFontName', FIG.font, ...
           'defaultLegendFontName', FIG.font, ...
           'defaultAxesFontSize', FIG.fontSize, 'defaultAxesLineWidth', FIG.axLineW);

hasStats = (exist('signrank', 'file') == 2) || license('test', 'Statistics_Toolbox');

%% ===== STEP 1: LOCATE METRIC FILES (all subject folders) =====
this_dir = fileparts(mfilename('fullpath'));
if isempty(this_dir), this_dir = pwd; end

files = dir(fullfile(this_dir, '**', '*_metrics.mat'));
if isempty(files)
    error(['No *_metrics.mat files found under %s\n' ...
           'Run compare_trials.m for each subject/speed/incline and save ' ...
           'the `metrics` variable first.'], this_dir);
end

% Keep ONLY files in a direct subject subfolder of this_dir (i.e. this_dir/<Subject>/),
% AND never anything under 'Old Version Data' (archived/backup copies). Either
% rule alone excludes the backups; both are applied to be explicit.
exclude_dirs = {'Old Version Data'};
keep = arrayfun(@(x) strcmp(fileparts(x.folder), this_dir) && ...
                     ~any(cellfun(@(e) contains(x.folder, e), exclude_dirs)), files);
if any(~keep)
    fprintf('Ignoring %d metrics file(s) in nested/backup folders (not direct subject folders).\n', ...
        sum(~keep));
end
files = files(keep);
if isempty(files)
    error('No *_metrics.mat files directly under a subject folder of %s', this_dir);
end

%% ===== STEP 2: BUILD SUBJECT-LEVEL TABLE D =====
% One row per Subject x Speed x Incline x Muscle x Condition.
Subject = {}; Speed = []; Incline = []; Muscle = {}; Condition = {};
Support = []; WholeCycle = []; Ncyc = [];

for f = 1:numel(files)
    S = load(fullfile(files(f).folder, files(f).name), 'metrics');
    if ~isfield(S, 'metrics'), continue; end
    m = S.metrics;
    for ci = 1:numel(m.conditions)
        for k = 1:4
            if is_ext_m(k), supv = m.ext_zone_mean(ci, k);
            else,           supv = m.flex_zone_mean(ci, k);
            end
            Subject{end+1,1}   = char(m.subject);   %#ok<*AGROW>
            Speed(end+1,1)     = m.speed;
            Incline(end+1,1)   = m.incline;
            Muscle{end+1,1}    = muscles{k};
            Condition{end+1,1} = m.conditions{ci};
            Support(end+1,1)   = supv;
            WholeCycle(end+1,1)= m.wholecycle_mean(ci, k);
            Ncyc(end+1,1)      = m.n_cycles(ci);
        end
    end
end
D = table(Subject, Speed, Incline, Muscle, Condition, Support, WholeCycle, Ncyc);

subs = unique(D.Subject);
Nsub = numel(subs);

%% ===== STEP 3: REPORT COVERAGE =====
fprintf('="*80\n');
fprintf('GROUP AGGREGATION\n');
fprintf('="*80\n');
fprintf('Metric files found : %d\n', numel(files));
fprintf('Subjects processed : %d\n', Nsub);
for si = 1:Nsub
    n_files = numel(unique(strcat(string(D.Speed(strcmp(D.Subject,subs{si}))), '_', ...
                                  string(D.Incline(strcmp(D.Subject,subs{si}))))));
    fprintf('   - %-12s (%d speed x incline conditions)\n', subs{si}, n_files);
end
fprintf('Statistics toolbox : %s\n\n', ternary(hasStats, 'available', 'NOT found (CI only)'));

writetable(D, fullfile(this_dir, 'metrics_long.csv'));
save(fullfile(this_dir, 'metrics_long.mat'), 'D');

% Optional: plot one participant's own metrics for an individual sanity check
if plot_individual
    plot_one_subject(files, individual_subject, muscles);
end

%% ===== STEP 4: PER-SUBJECT % REDUCTION vs NO-EXO (pooled over walking conds) =====
% redA/redI: [Nsub x 4], reduction of Active/Inactive relative to No-Exo.
[redA, redI]       = deal(nan(Nsub, 4));   % support DV
[redA_wc, redI_wc] = deal(nan(Nsub, 4));   % whole-cycle DV

for si = 1:Nsub
    for k = 1:4
        sel = strcmp(D.Subject, subs{si}) & strcmp(D.Muscle, muscles{k});
        gp = @(col,c) mean(col(sel & strcmp(D.Condition, c)), 'omitnan');

        no = gp(D.Support,'noexo'); ac = gp(D.Support,'exoactive'); ia = gp(D.Support,'exoinactive');
        if ~isnan(no) && no ~= 0
            redA(si,k) = (no-ac)/no*100;
            redI(si,k) = (no-ia)/no*100;
        end
        nw = gp(D.WholeCycle,'noexo'); aw = gp(D.WholeCycle,'exoactive'); iw = gp(D.WholeCycle,'exoinactive');
        if ~isnan(nw) && nw ~= 0
            redA_wc(si,k) = (nw-aw)/nw*100;
            redI_wc(si,k) = (nw-iw)/nw*100;
        end
    end
end

%% ===== STEP 5: GROUP STATS + SIGNIFICANCE (per muscle) =====
% Question per muscle: across the N subjects, is the % reduction vs No-Exo
% reliably different from 0? Paired within-subject design -> Wilcoxon signed-rank
% on the per-subject reductions (nonparametric, robust at small N). q = the
% p-value AFTER Benjamini-Hochberg FDR correction across the 4 muscles.
% dz = Cohen's effect size (mean/SD). SIGNIFICANT means q < alpha.
alpha = 0.05;
pA = nan(1,4); pI = nan(1,4); dzA = nan(1,4); dzI = nan(1,4);
for k = 1:4
    xa = redA(~isnan(redA(:,k)),k);
    xi = redI(~isnan(redI(:,k)),k);
    dzA(k) = effect_dz(xa);  dzI(k) = effect_dz(xi);
    if hasStats
        if numel(xa) >= 2, pA(k) = signrank(xa); end
        if numel(xi) >= 2, pI(k) = signrank(xi); end
    end
end
qA = bh_fdr(pA);  qI = bh_fdr(pI);   % FDR across the 4 muscles

fprintf('=== SUPPORT-ZONE REDUCTION vs No-Exo  (N = %d subjects) ===\n', size(redA,1));
fprintf('Positive mean%% = exosuit REDUCED activity (support). q = FDR-corrected signed-rank p.\n\n');
fprintf('%-4s | %-30s | %-30s\n', 'Musc', 'ACTIVE  vs No-Exo', 'INACTIVE vs No-Exo');
fprintf('%-4s | %7s %6s %6s %-8s | %7s %6s %6s %-8s\n', ...
        '', 'mean%','dz','q','verdict', 'mean%','dz','q','verdict');
for k = 1:4
    mA = mean(redA(:,k),'omitnan'); mI = mean(redI(:,k),'omitnan');
    fprintf('%-4s | %6.1f%% %6.2f %6.3f %-8s | %6.1f%% %6.2f %6.3f %-8s\n', ...
        muscles{k}, mA, dzA(k), qA(k), sig_label(qA(k),alpha), ...
                    mI, dzI(k), qI(k), sig_label(qI(k),alpha));
end

fprintf('\n--- PLAIN-ENGLISH VERDICT (Active exosuit vs No-Exo) ---\n');
for k = 1:4
    mA = mean(redA(:,k),'omitnan');
    if isnan(qA(k))
        fprintf('  %-4s: no test (Statistics Toolbox missing).\n', muscles{k});
    elseif qA(k) < alpha && mA > 0
        fprintf('  %-4s: SIGNIFICANT reduction of %.1f%%  (q = %.3f, dz = %.2f).\n', ...
            muscles{k}, mA, qA(k), dzA(k));
    elseif qA(k) < alpha && mA < 0
        fprintf('  %-4s: SIGNIFICANT INCREASE of %.1f%%  (q = %.3f).\n', muscles{k}, -mA, qA(k));
    else
        fprintf('  %-4s: NOT significant  (mean %.1f%%, q = %.3f).\n', muscles{k}, mA, qA(k));
    end
end
fprintf('\n');

%% ===== STEP 6: MIXED MODELS — generalization across speed/incline/subjects =====
lmeActEst = nan(1,4); lmeActP = nan(1,4);      % Active vs No-Exo (model estimate, p)
lmeInactEst = nan(1,4); lmeInactP = nan(1,4);  % Inactive vs No-Exo
genConsistent = true(1,4);                     % effect consistent across walking conds?
if hasStats
    fprintf('=== MIXED MODELS: Support ~ Condition*Speed + Condition*Incline + (1|Subject) ===\n');
    for k = 1:4
        sub = D(strcmp(D.Muscle, muscles{k}), :);
        if numel(unique(sub.Subject)) < 2 || height(sub) < 8
            fprintf('  %s: insufficient data, skipped.\n', muscles{k}); continue;
        end
        sub.Condition = categorical(sub.Condition, cond_list);
        sub.Speed     = categorical(sub.Speed);
        sub.Incline   = categorical(sub.Incline);
        sub.Subject   = categorical(sub.Subject);
        try
            lme = fitlme(sub, 'Support ~ Condition*Speed + Condition*Incline + (1|Subject)');
            nm = lme.Coefficients.Name; est = lme.Coefficients.Estimate; pv = lme.Coefficients.pValue;
            fprintf('----- %s -----\n', muscles{k});
            interact_sig = false;
            for r = 1:numel(nm)
                nmr = nm{r}; isInter = contains(nmr, ':');
                if contains(nmr,'Condition_exoactive') && ~isInter
                    lmeActEst(k) = est(r); lmeActP(k) = pv(r);
                    fprintf('   Active   vs No-Exo : est = %7.2f %%MVC,  p = %.3f  -> %s\n', ...
                        est(r), pv(r), sig_label(pv(r),alpha));
                elseif contains(nmr,'Condition_exoinactive') && ~isInter
                    lmeInactEst(k) = est(r); lmeInactP(k) = pv(r);
                    fprintf('   Inactive vs No-Exo : est = %7.2f %%MVC,  p = %.3f  -> %s\n', ...
                        est(r), pv(r), sig_label(pv(r),alpha));
                elseif isInter && contains(nmr,'Condition') && pv(r) < alpha
                    interact_sig = true;
                end
            end
            genConsistent(k) = ~interact_sig;
            if interact_sig
                fprintf('   Across walking conds: a Condition x Speed/Incline term is SIGNIFICANT => effect VARIES.\n');
            else
                fprintf('   Across walking conds: no significant interaction => effect is CONSISTENT.\n');
            end
        catch ME
            fprintf('  %s: model failed (%s).\n', muscles{k}, ME.message);
        end
    end
    fprintf(['\nNote: est is in %%MVC (negative = lower activity than No-Exo). ' ...
             'A significant Condition row = real effect controlling for speed/incline/subject.\n\n']);
else
    fprintf('[Mixed models skipped: Statistics Toolbox not available.]\n\n');
end

%% ===== STEPS 7-9: GROUP FIGURES (skipped when verifying an individual) =====
if ~plot_individual

% Figure window names below MATCH the LaTeX \includegraphics filenames, so the
% window titled e.g. "group_activity_slopegraph" is saved as
% figures/group_activity_slopegraph.png. Set FIG.save = true to export them
% automatically. Panels carry no descriptive title (that lives in the caption).
figHandles = struct();

%% ===== STEP 7: SLOPEGRAPH — activity across conditions (per participant) =====
figHandles.group_activity_slopegraph = ...
    plot_slope(D, subs, muscles, cond_list, FIG);

%% ===== STEP 7b: DOT-WHISKER — FUNCTIONAL-ZONE % reduction (Active & Inactive) =====
figHandles.group_reduction_forest = plot_reduction_forest(redA, redI, muscles, qA, qI, ...
    'Reduction vs No-Exo (%)', 'group_reduction_forest', FIG.cActive, FIG);

%% ===== STEP 8: DOT-WHISKER (SUPPLEMENT) — WHOLE-CYCLE % reduction =====
% Teal accent so it is not confused with the functional-zone figure.
qA_wc = bh_fdr(arrayfun(@(k) signrank_safe(redA_wc(:,k), hasStats), 1:4));
qI_wc = bh_fdr(arrayfun(@(k) signrank_safe(redI_wc(:,k), hasStats), 1:4));
figHandles.group_reduction_wholecycle_supp = plot_reduction_forest(redA_wc, redI_wc, ...
    muscles, qA_wc, qI_wc, 'Reduction vs No-Exo (%)', ...
    'group_reduction_wholecycle_supp', [0.20 0.60 0.55], FIG);

%% ===== STEP 9: FIGURE 3 (SUPPLEMENT) — generalization across walking conds =====
[wc, ~] = unique([D.Incline D.Speed], 'rows');
Nw = size(wc, 1);
wc_lab = arrayfun(@(i) sprintf('inc%d/spd%.1f', wc(i,1), wc(i,2)), 1:Nw, 'uni', 0);
redA_w = nan(Nsub, 4, Nw);   % Active-vs-noexo reduction per walking condition
for iw = 1:Nw
    for si = 1:Nsub
        for k = 1:4
            sel = D.Incline==wc(iw,1) & D.Speed==wc(iw,2) & ...
                  strcmp(D.Subject,subs{si}) & strcmp(D.Muscle,muscles{k});
            no = mean(D.Support(sel & strcmp(D.Condition,'noexo')),      'omitnan');
            ac = mean(D.Support(sel & strcmp(D.Condition,'exoactive')),  'omitnan');
            if ~isnan(no) && no ~= 0, redA_w(si,k,iw) = (no-ac)/no*100; end
        end
    end
end

% HEATMAP of mean reduction (muscles x walking conditions). A single-colour
% scale keeps it from looking like separate case studies; near-uniform colour
% along a muscle's row means the effect generalizes. Cells show the mean %.
Hmat = nan(4, Nw);
for k = 1:4
    for iw = 1:Nw
        Hmat(k,iw) = mean(redA_w(:,k,iw), 1, 'omitnan');
    end
end
% incline code -> road grade for display (0 -> 0%%, 5 -> 10%% grade)
wc_lab2 = arrayfun(@(i) sprintf('%d%%, %.1f', (wc(i,1)>0)*10, wc(i,2)), 1:Nw, 'uni', 0);
greens = [linspace(1,0.30,64)', linspace(1,0.62,64)', linspace(1,0.34,64)'];  % white -> green

figHandles.generalization_walkingconds = figure('Name','generalization_walkingconds', ...
    'Color','w','Units','centimeters','Position',[2 2 FIG.figW1col+3.5 FIG.figH1]);
imagesc(Hmat); colormap(greens);
cb = colorbar; cb.Label.String = 'Reduction vs No-Exo (%)';
climmax = max(Hmat(:)); if ~(climmax>0), climmax = 1; end
clim([min(0,min(Hmat(:))) climmax]);
for k = 1:4
    for iw = 1:Nw
        text(iw, k, sprintf('%.0f', Hmat(k,iw)), 'HorizontalAlignment','center', ...
            'Color',[0 0 0], 'FontWeight','bold', 'FontSize',FIG.fontSize-1);
    end
end
set(gca,'XTick',1:Nw,'XTickLabel',wc_lab2,'YTick',1:4,'YTickLabel',muscles, ...
    'TickLength',[0 0]);
xlabel('Walking condition (grade, speed m/s)');

% ---- Optional auto-export: each figure -> FIG.dir/<windowname>.<fmt> ----
% Use exportgraphics (NOT File>Save As / screenshots, which are low-res). PDF is
% vector = sharpest for a LaTeX line figure; PNG is written at FIG.dpi.
if FIG.save
    outdir = fullfile(this_dir, FIG.dir);
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    fn = fieldnames(figHandles);
    for i = 1:numel(fn)
        save_fig(figHandles.(fn{i}), fullfile(outdir, [fn{i} '.' FIG.fmt]), FIG.fmt, FIG.dpi);
    end
    fprintf('Exported %d figures (%s) to %s\n', numel(fn), upper(FIG.fmt), outdir);
end

end  % ~plot_individual (group figures suppressed while verifying one participant)

%% ===== STEP 10: SAVE GROUP SUMMARY =====
Grp = table(muscles', mean(redA,1,'omitnan')', arrayfun(@(k)ci95(redA(:,k)),1:4)', qA', dzA', ...
                       mean(redI,1,'omitnan')', arrayfun(@(k)ci95(redI(:,k)),1:4)', qI', dzI', ...
    'VariableNames', {'Muscle','Active_mean','Active_CI','Active_q','Active_dz', ...
                      'Inactive_mean','Inactive_CI','Inactive_q','Inactive_dz'});
writetable(Grp, fullfile(this_dir, 'group_reduction_summary.csv'));
fprintf('Saved: metrics_long.csv, group_reduction_summary.csv, and figures.\n');
fprintf('Subjects included: %d\n', Nsub);

%% ===== STEP 11: COPY-PASTEABLE RESULTS REPORT (for writing the paper) =====
% Builds a single self-contained text block (also saved to results_report.txt)
% with everything needed to frame the Results section. Copy the block between
% the >>> markers and paste it to Claude.

% Descriptive whole-cycle activity per condition: per-subject mean over walking
% conditions, then group mean +/- SD across subjects.
condK = {'noexo','exoinactive','exoactive'};
absMean = nan(4,3); absSD = nan(4,3);
for k = 1:4
    for c = 1:3
        v = nan(Nsub,1);
        for si = 1:Nsub
            sel = strcmp(D.Subject,subs{si}) & strcmp(D.Muscle,muscles{k}) & strcmp(D.Condition,condK{c});
            v(si) = mean(D.WholeCycle(sel), 'omitnan');
        end
        absMean(k,c) = mean(v,'omitnan'); absSD(k,c) = std(v,'omitnan');
    end
end

R = '';
R = [R sprintf('\n>>> COPY FROM HERE — RESULTS REPORT >>>\n')];
R = [R sprintf('STUDY: N = %d subjects; 3 conditions (No-Exo, Exo-Inactive, Exo-Active);\n', Nsub)];
R = [R sprintf('       4 walking conditions (grade 0%%/10%% x speed 0.8/1.2 m/s).\n')];
R = [R sprintf('SUBJECTS: %s\n', strjoin(subs, ', '))];
R = [R sprintf('DV: whole-cycle mean EMG (%%MVC). SUPPORT DV: each muscle in its functional zone\n')];
R = [R sprintf('    (VL,RF = extension phase; BF,ST = flexion phase).\n')];
R = [R sprintf('TESTS: Wilcoxon signed-rank on per-subject %% reductions, Benjamini-Hochberg FDR\n')];
R = [R sprintf('       across 4 muscles (q). Linear mixed models for generalization. alpha = %.2f.\n', alpha)];
R = [R sprintf('SIG CODES: *** q<.001, ** q<.01, * q<.05, n.s. = not significant.\n\n')];

R = [R sprintf('[TABLE A] Whole-cycle activity (%%MVC), group mean +/- SD across subjects:\n')];
R = [R sprintf('%-4s | %14s | %14s | %14s\n','Musc','No-Exo','Exo-Inactive','Exo-Active')];
for k = 1:4
    R = [R sprintf('%-4s | %6.1f +- %-4.1f | %6.1f +- %-4.1f | %6.1f +- %-4.1f\n', muscles{k}, ...
        absMean(k,1),absSD(k,1), absMean(k,2),absSD(k,2), absMean(k,3),absSD(k,3))];
end

R = [R sprintf('\n[TABLE B] SUPPORT-ZONE %% reduction vs No-Exo (pooled over walking conds):\n')];
R = [R sprintf('%-4s | %-28s | %-28s\n','Musc','ACTIVE','INACTIVE')];
R = [R sprintf('%-4s | %7s %8s %5s %-6s | %7s %8s %5s %-6s\n','','mean%','95%CI','dz','q', 'mean%','95%CI','dz','q')];
for k = 1:4
    R = [R sprintf('%-4s | %6.1f%% +-%4.1f %5.2f %5.3f | %6.1f%% +-%4.1f %5.2f %5.3f\n', muscles{k}, ...
        mean(redA(:,k),'omitnan'), ci95(redA(:,k)), dzA(k), qA(k), ...
        mean(redI(:,k),'omitnan'), ci95(redI(:,k)), dzI(k), qI(k))];
end

R = [R sprintf('\n[TABLE C] MIXED-EFFECTS MODEL per muscle (est in %%MVC vs No-Exo; neg = lower):\n')];
if hasStats
    R = [R sprintf('%-4s | %-22s | %-22s | %s\n','Musc','Active vs No-Exo','Inactive vs No-Exo','across walking conds')];
    for k = 1:4
        R = [R sprintf('%-4s | est %7.2f p=%.3f %-4s | est %7.2f p=%.3f %-4s | %s\n', muscles{k}, ...
            lmeActEst(k), lmeActP(k), sig_label(lmeActP(k),alpha), ...
            lmeInactEst(k), lmeInactP(k), sig_label(lmeInactP(k),alpha), ...
            ternary(genConsistent(k),'CONSISTENT','VARIES'))];
    end
else
    R = [R sprintf('(Statistics Toolbox not available — mixed models not run.)\n')];
end
R = [R sprintf('\nNote: positive reduction%% = exosuit lowered activity (support). q = FDR-corrected.\n')];
R = [R sprintf('<<< COPY TO HERE <<<\n\n')];

fprintf('%s', R);
fid = fopen(fullfile(this_dir, 'results_report.txt'), 'w');
if fid > 0, fprintf(fid, '%s', R); fclose(fid);
    fprintf('Full report also saved to results_report.txt\n');
end

%% ============================ LOCAL FUNCTIONS ============================
function save_fig(h, file, fmt, dpi)
    % Export a FIGURE robustly across MATLAB versions. exportgraphics accepts a
    % figure only in R2020b+; on older releases it errors ("First parameter must
    % specify the axes or chart object"), so we fall back to print(), which takes
    % a figure handle everywhere.
    try
        if strcmpi(fmt, 'pdf')
            exportgraphics(h, file, 'ContentType', 'vector');
        else
            exportgraphics(h, file, 'Resolution', dpi);
        end
    catch
        set(h, 'Units', 'centimeters'); p = get(h, 'Position');
        set(h, 'PaperUnits', 'centimeters', 'PaperPositionMode', 'manual', ...
            'PaperSize', [p(3) p(4)], 'PaperPosition', [0 0 p(3) p(4)]);
        if strcmpi(fmt, 'pdf')
            print(h, file, '-dpdf', '-painters');          % vector PDF
        else
            print(h, file, '-dpng', sprintf('-r%d', dpi)); % high-res raster
        end
    end
end

function plot_one_subject(files, subj, muscles)
    % Plot ONE participant's WHOLE-CYCLE average muscle activity across walking
    % conditions, with stride-to-stride SD, plus their No-Exo -> Active reduction.
    got = {};
    for f = 1:numel(files)
        S = load(fullfile(files(f).folder, files(f).name), 'metrics');
        if isfield(S,'metrics') && strcmpi(char(S.metrics.subject), subj)
            got{end+1} = S.metrics;   %#ok<AGROW>
        end
    end
    if isempty(got)
        warning('plot_individual: no metrics files found for subject "%s".', subj);
        return;
    end

    % order panels by incline then speed
    inc = cellfun(@(m) m.incline, got); spd = cellfun(@(m) m.speed, got);
    [~, ord] = sortrows([inc(:) spd(:)]); got = got(ord);
    Nw = numel(got);
    wc_lab = cellfun(@(m) sprintf('inc%d/%.1f', m.incline, m.speed), got, 'uni', 0);
    cond_colors = [0.60 0.60 0.60; 0.47 0.67 0.19; 0.30 0.75 0.93];
    cond_leg = {'No-Exo', 'Exo Inactive', 'Exo Active'};

    figure('Name', sprintf('individual_%s', subj), 'Color','w', 'Position',[90 90 1600 820]);
    for k = 1:4
        M = nan(Nw,3); Sd = nan(Nw,3);
        for iw = 1:Nw
            m = got{iw};
            M(iw,:)  = m.wholecycle_mean(:,k)';   % whole-cycle average activity
            Sd(iw,:) = m.wholecycle_sd(:,k)';     % stride-to-stride SD
        end

        % top: grouped bars (walking cond x condition) with stride-to-stride SD
        subplot(2,4,k); hold on;
        hb = bar(M, 'grouped');
        for c = 1:3
            hb(c).FaceColor = cond_colors(c,:);
            xe = hb(c).XEndPoints;
            errorbar(xe, M(:,c), Sd(:,c), 'k','linestyle','none', ...
                'CapSize',4,'LineWidth',1,'HandleVisibility','off');
        end
        set(gca,'XTick',1:Nw,'XTickLabel',wc_lab,'XTickLabelRotation',25);
        title(muscles{k},'FontWeight','bold');
        if k==1, ylabel('Avg activity (% MVC)'); legend(cond_leg,'Location','best'); end
        grid on; box off; ylim([0 inf]);

        % bottom: reduction vs No-Exo for Active AND Inactive, per walking
        % condition (NO averaging across conditions).
        subplot(2,4,4+k); hold on;
        R = nan(Nw,2);   % col1 = Active, col2 = Inactive
        for iw = 1:Nw
            no = M(iw,1);
            if ~isnan(no) && no ~= 0
                R(iw,1) = (no - M(iw,3)) / no * 100;   % No-Exo -> Active
                R(iw,2) = (no - M(iw,2)) / no * 100;   % No-Exo -> Inactive
            end
        end
        hr = bar(R, 'grouped');
        hr(1).FaceColor = [0.30 0.75 0.93]; hr(1).DisplayName = 'Active';
        hr(2).FaceColor = [0.72 0.72 0.72]; hr(2).DisplayName = 'Inactive';
        yline(0,'k-','HandleVisibility','off');
        set(gca,'XTick',1:Nw,'XTickLabel',wc_lab,'XTickLabelRotation',25);
        if k==1, ylabel('% reduction vs No-Exo'); legend('Location','best'); end
        grid on; box off;
    end
end

function hf = plot_slope(D, subs, muscles, cond_list, FIG)
    % SLOPEGRAPH. 2x2 muscles. Faint gray lines = individual participants across
    % No-Exo -> Inactive -> Active (whole-cycle %MVC, pooled over walking conds);
    % bold blue = group mean +/- 95% CI; green arrow marks the mean reduction.
    % Per-panel muscle name kept as an identifier; no descriptive title.
    Nsub = numel(subs); xC = 1:3;
    condLab = {'No-Exo','Inactive','Active'};
    gcol = [0.13 0.60 0.20];

    hf = figure('Name','group_activity_slopegraph','Color','w', ...
        'Units','centimeters','Position',[2 2 FIG.figW2col FIG.figH2]);
    for k = 1:4
        subplot(2,2,k); hold on;
        V = nan(Nsub,3);
        for si = 1:Nsub
            for c = 1:3
                sel = strcmp(D.Subject,subs{si}) & strcmp(D.Muscle,muscles{k}) & ...
                      strcmp(D.Condition,cond_list{c});
                V(si,c) = mean(D.WholeCycle(sel),'omitnan');
            end
            % faint, thin, no markers -> much less clutter than before
            plot(xC, V(si,:), '-', 'Color',[0.84 0.84 0.84], 'LineWidth',0.75, ...
                'HandleVisibility','off');
        end
        gm = mean(V,1,'omitnan');
        gc = arrayfun(@(c) ci95(V(:,c)), xC);
        errorbar(xC, gm, gc, '-o', 'Color',FIG.cActive, 'MarkerFaceColor',FIG.cActive, ...
            'MarkerSize',7, 'LineWidth',FIG.lineW+0.4, 'CapSize',7, 'HandleVisibility','off');

        % Faint dashed reference lines from the No-Exo and Active means extended
        % to the RIGHT margin, with a SMALL green arrow + horizontal % marking
        % the reduction.
        if gm(1) > 0
            red = (gm(1)-gm(3))/gm(1)*100; xR = 3.40;
            plot([1 xR], [gm(1) gm(1)], '--', 'Color',[0.55 0.55 0.55], ...
                'LineWidth',0.8, 'HandleVisibility','off');
            plot([3 xR], [gm(3) gm(3)], '--', 'Color',[0.55 0.55 0.55], ...
                'LineWidth',0.8, 'HandleVisibility','off');
            plot([xR xR], [gm(1) gm(3)], '-', 'Color',gcol, 'LineWidth',1.6, ...
                'HandleVisibility','off');                         % arrow shaft
            plot(xR, gm(3), 'v', 'Color',gcol, 'MarkerFaceColor',gcol, ...
                'MarkerSize',5, 'HandleVisibility','off');         % small fixed arrowhead
            text(xR+0.12, mean([gm(1) gm(3)]), sprintf('%.0f%%', red), ...
                'Color',gcol, 'FontWeight','bold', 'FontSize',FIG.fontSize-2, ...
                'HorizontalAlignment','left', 'VerticalAlignment','middle');
        end
        set(gca,'XTick',xC,'XTickLabel',condLab); xlim([0.7 4.2]);
        title(muscles{k},'FontWeight','bold');
        if k==1 || k==3, ylabel('Activity (% MVC)'); end
        box off; ylim([0 inf]);
    end
end

function hf = plot_reduction_forest(redA, redI, muscles, qA, qI, ylab, figname, actCol, FIG)
    % DOT-AND-WHISKER. Per muscle: Active (actCol) and Inactive (gray) mean %
    % reduction with 95% CI whiskers; light dots = participants; FDR stars above.
    % No descriptive title (that lives in the caption); muscles are on the x-axis.
    X = 1:4; off = 0.16; Nsub = size(redA,1);
    mA = mean(redA,1,'omitnan'); mI = mean(redI,1,'omitnan');
    cA = arrayfun(@(k) ci95(redA(:,k)), X);
    cI = arrayfun(@(k) ci95(redI(:,k)), X);

    hf = figure('Name',figname,'Color','w', ...
        'Units','centimeters','Position',[2 2 FIG.figW1col FIG.figH1]); hold on;
    yline(0, '-', 'Color',[0.75 0.75 0.75], 'LineWidth',1.0, 'HandleVisibility','off');

    for k = X   % individual-participant dots (small, faint)
        jt = (rand(Nsub,1)-0.5)*0.09;
        scatter((k-off)+jt, redA(:,k), FIG.markerSz*0.30, actCol, 'filled', ...
            'MarkerFaceAlpha',0.22, 'HandleVisibility','off');
        scatter((k+off)+jt, redI(:,k), FIG.markerSz*0.30, FIG.cInactive, 'filled', ...
            'MarkerFaceAlpha',0.25, 'HandleVisibility','off');
    end
    % Distinct SHAPES so the legend cannot be mistaken for data: Active = circle,
    % Inactive = square. Smaller mean markers.
    errorbar(X-off, mA, cA, 'o', 'Color',actCol, 'MarkerFaceColor',actCol, ...
        'MarkerSize',5.5, 'LineWidth',FIG.lineW-0.4, 'CapSize',5, 'DisplayName','Active');
    errorbar(X+off, mI, cI, 's', 'Color',FIG.cInactive, 'MarkerFaceColor',FIG.cInactive, ...
        'MarkerSize',6, 'LineWidth',FIG.lineW-0.4, 'CapSize',5, 'DisplayName','Inactive');

    for k = X   % FDR significance stars
        sA = stars(qA(k));
        if ~isempty(sA), text(k-off, mA(k)+cA(k)+4, sA, 'HorizontalAlignment','center', ...
                'FontSize',FIG.fontSize); end
        sI = stars(qI(k));
        if ~isempty(sI), text(k+off, mI(k)+cI(k)+4, sI, 'HorizontalAlignment','center', ...
                'FontSize',FIG.fontSize); end
    end
    set(gca,'XTick',X,'XTickLabel',muscles); xlim([0.5 4.5]);
    ylabel(ylab);
    % legend OUTSIDE the data area so it is not confused with the markers
    legend('Location','northoutside','Orientation','horizontal','Box','off');
    box off;
end

function c = ci95(x)
    x = x(~isnan(x)); n = numel(x);
    if n < 2, c = 0; return; end
    c = tcrit95(n-1) * std(x) / sqrt(n);
end

function [m,c] = mean_ci(x)
    m = mean(x,'omitnan'); c = ci95(x);
end

function dz = effect_dz(x)
    x = x(~isnan(x));
    if numel(x) < 2 || std(x) == 0, dz = NaN; else, dz = mean(x)/std(x); end
end

function p = signrank_safe(x, hasStats)
    x = x(~isnan(x));
    if hasStats && numel(x) >= 2, p = signrank(x); else, p = NaN; end
end

function q = bh_fdr(p)
    p = p(:)'; m = numel(p); q = nan(1,m);
    ok = ~isnan(p); pp = p(ok); mm = numel(pp);
    if mm == 0, return; end
    [ps, ix] = sort(pp); qs = ps .* mm ./ (1:mm);
    for i = mm-1:-1:1, qs(i) = min(qs(i), qs(i+1)); end
    qv = nan(1,mm); qv(ix) = min(qs,1);
    q(ok) = qv;
end

function tc = tcrit95(df)
    if df < 1, tc = NaN; return; end
    if exist('tinv','file') == 2, tc = tinv(0.975, df); return; end
    tbl = [12.71 4.303 3.182 2.776 2.571 2.447 2.365 2.306 2.262 2.228];
    if df <= 10, tc = tbl(df);
    elseif df <= 20, tc = 2.086;
    elseif df <= 30, tc = 2.042;
    else, tc = 1.96; end
end

function s = stars(p)
    if isnan(p), s = ''; elseif p < 0.001, s = '***';
    elseif p < 0.01, s = '**'; elseif p < 0.05, s = '*'; else, s = ''; end
end

function s = sig_label(q, alpha)
    if isnan(q),        s = 'n/a';
    elseif q < 0.001,   s = '*** sig';
    elseif q < 0.01,    s = '**  sig';
    elseif q < alpha,   s = '*   sig';
    else,               s = 'n.s.';
    end
end

function out = ternary(cond, a, b)
    if cond, out = a; else, out = b; end
end
