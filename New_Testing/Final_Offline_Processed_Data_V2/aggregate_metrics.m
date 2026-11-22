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
plot_individual    = false;
individual_subject = 'Amir';    % must match metrics.subject

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
                    fprintf('   Active   vs No-Exo : est = %7.2f %%MVC,  p = %.3f  -> %s\n', ...
                        est(r), pv(r), sig_label(pv(r),alpha));
                elseif contains(nmr,'Condition_exoinactive') && ~isInter
                    fprintf('   Inactive vs No-Exo : est = %7.2f %%MVC,  p = %.3f  -> %s\n', ...
                        est(r), pv(r), sig_label(pv(r),alpha));
                elseif isInter && contains(nmr,'Condition') && pv(r) < alpha
                    interact_sig = true;
                end
            end
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

%% ===== STEP 7: CENTRAL FIGURE — grouped conditions x walking conds (+ reduction row) =====
% Top row (per muscle): grouped bars, 4 walking conditions x {noexo, inactive,
% active}, group mean +/- 95% CI with individual-subject dots overlaid.
% Bottom row (per muscle): No-Exo -> Active % reduction per walking condition.
plot_central(D, subs, muscles, cond_list);

%% ===== STEP 7b: FIGURE — pooled support-zone % reduction (Active & Inactive) =====
plot_reduction_bars(redA, redI, muscles, qA, qI, ...
    'Muscle activity reduction vs No-Exo  (support zone, group mean \pm 95% CI)');

%% ===== STEP 8: FIGURE 2 (SUPPLEMENT) — whole-cycle % reduction =====
qA_wc = bh_fdr(arrayfun(@(k) signrank_safe(redA_wc(:,k), hasStats), 1:4));
qI_wc = bh_fdr(arrayfun(@(k) signrank_safe(redI_wc(:,k), hasStats), 1:4));
plot_reduction_bars(redA_wc, redI_wc, muscles, qA_wc, qI_wc, ...
    'Whole-cycle activity reduction vs No-Exo  (supplementary)');

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

figure('Name','Generalization across walking conditions','Color','w','Position',[120 120 1500 420]);
for k = 1:4
    subplot(1,4,k); hold on;
    mvals = mean(redA_w(:,k,:), 1, 'omitnan'); mvals = mvals(:)';
    cvals = arrayfun(@(iw) ci95(redA_w(:,k,iw)), 1:Nw);
    bar(1:Nw, mvals, 'FaceColor',[0.30 0.75 0.93]);
    errorbar(1:Nw, mvals, cvals, 'k', 'linestyle','none','LineWidth',1.2,'CapSize',6);
    yline(0,'k-');
    set(gca,'XTick',1:Nw,'XTickLabel',wc_lab,'XTickLabelRotation',30);
    title(muscles{k},'FontWeight','bold'); if k==1, ylabel('% reduction vs No-Exo (Active)'); end
    grid on; box off;
end
sgtitle('Active-exosuit support by walking condition (group mean \pm 95% CI)','FontWeight','bold');

end  % ~plot_individual (group figures suppressed while verifying one participant)

%% ===== STEP 10: SAVE GROUP SUMMARY =====
Grp = table(muscles', mean(redA,1,'omitnan')', arrayfun(@(k)ci95(redA(:,k)),1:4)', qA', dzA', ...
                       mean(redI,1,'omitnan')', arrayfun(@(k)ci95(redI(:,k)),1:4)', qI', dzI', ...
    'VariableNames', {'Muscle','Active_mean','Active_CI','Active_q','Active_dz', ...
                      'Inactive_mean','Inactive_CI','Inactive_q','Inactive_dz'});
writetable(Grp, fullfile(this_dir, 'group_reduction_summary.csv'));
fprintf('Saved: metrics_long.csv, group_reduction_summary.csv, and figures.\n');
fprintf('Subjects included: %d\n', Nsub);

%% ============================ LOCAL FUNCTIONS ============================
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

    figure('Name', sprintf('Individual: %s', subj), 'Color','w', 'Position',[90 90 1600 820]);
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

        % bottom: No-Exo -> Active reduction per walking condition
        subplot(2,4,4+k); hold on;
        red = nan(1,Nw);
        for iw = 1:Nw
            no = M(iw,1); ac = M(iw,3);
            if ~isnan(no) && no ~= 0, red(iw) = (no-ac)/no*100; end
        end
        bar(1:Nw, red, 'FaceColor',[0.30 0.75 0.93]);
        yline(0,'k-');
        set(gca,'XTick',1:Nw,'XTickLabel',wc_lab,'XTickLabelRotation',25);
        if k==1, ylabel('% reduction (No-Exo \rightarrow Active)'); end
        grid on; box off;
    end
    sgtitle(sprintf('Individual participant: %s  (whole-cycle average activity, error = stride-to-stride SD)', subj), ...
        'FontWeight','bold');
end

function plot_central(D, subs, muscles, cond_list)
    % 2 rows x 4 muscles. Top: grouped bars (walking cond x exo condition) with
    % subject dots. Bottom: No-Exo -> Active % reduction per walking condition.
    Nsub = numel(subs);
    [wc, ~] = unique([D.Incline D.Speed], 'rows');
    Nw = size(wc, 1);
    wc_lab = arrayfun(@(i) sprintf('inc%d/%.1f', wc(i,1), wc(i,2)), 1:Nw, 'uni', 0);
    cond_colors = [0.60 0.60 0.60; 0.47 0.67 0.19; 0.30 0.75 0.93];  % noexo, inact, active
    cond_leg = {'No-Exo', 'Exo Inactive', 'Exo Active'};

    figure('Name','Central: conditions x walking conditions','Color','w', ...
        'Position',[80 60 1600 820]);

    for k = 1:4
        % ---- gather subject-level support values: Mk(Nw x 3), dots ----
        Mk = nan(Nw,3); Ck = nan(Nw,3); sv = cell(Nw,3);
        for iw = 1:Nw
            for c = 1:3
                vals = nan(Nsub,1);
                for si = 1:Nsub
                    sel = D.Incline==wc(iw,1) & D.Speed==wc(iw,2) & ...
                          strcmp(D.Subject,subs{si}) & strcmp(D.Muscle,muscles{k}) & ...
                          strcmp(D.Condition,cond_list{c});
                    vals(si) = mean(D.Support(sel), 'omitnan');
                end
                Mk(iw,c) = mean(vals,'omitnan'); Ck(iw,c) = ci95(vals); sv{iw,c} = vals;
            end
        end

        % ---- TOP ROW: grouped bars + dots ----
        subplot(2,4,k); hold on;
        hb = bar(Mk, 'grouped');
        for c = 1:3
            hb(c).FaceColor = cond_colors(c,:);
            xe = hb(c).XEndPoints;                          % 1 x Nw
            errorbar(xe, Mk(:,c), Ck(:,c), 'k','linestyle','none', ...
                'CapSize',4,'LineWidth',1,'HandleVisibility','off');
            for iw = 1:Nw
                v = sv{iw,c}; jt = (rand(numel(v),1)-0.5)*0.06;
                scatter(xe(iw)+jt, v, 12, [0.15 0.15 0.15], 'filled', ...
                    'MarkerFaceAlpha',0.5, 'HandleVisibility','off');
            end
        end
        set(gca,'XTick',1:Nw,'XTickLabel',wc_lab,'XTickLabelRotation',25);
        title(muscles{k},'FontWeight','bold');
        if k==1, ylabel('Support-zone activity (% MVC)'); legend(cond_leg,'Location','best'); end
        grid on; box off; ylim([0 inf]);

        % ---- BOTTOM ROW: No-Exo -> Active reduction per walking condition ----
        subplot(2,4,4+k); hold on;
        rmean = nan(1,Nw); rci = nan(1,Nw); rsv = cell(1,Nw);
        for iw = 1:Nw
            no = sv{iw,1}; ac = sv{iw,3};
            r = (no - ac) ./ no * 100; r(no==0) = NaN;
            rmean(iw) = mean(r,'omitnan'); rci(iw) = ci95(r); rsv{iw} = r;
        end
        hbar = bar(1:Nw, rmean, 'FaceColor',[0.30 0.75 0.93]);  %#ok<NASGU>
        errorbar(1:Nw, rmean, rci, 'k','linestyle','none','CapSize',5,'LineWidth',1);
        for iw = 1:Nw
            v = rsv{iw}; jt = (rand(numel(v),1)-0.5)*0.08;
            scatter(iw+jt, v, 14, [0.15 0.15 0.15], 'filled','MarkerFaceAlpha',0.5);
        end
        yline(0,'k-');
        set(gca,'XTick',1:Nw,'XTickLabel',wc_lab,'XTickLabelRotation',25);
        if k==1, ylabel('% reduction (No-Exo \rightarrow Active)'); end
        grid on; box off;
    end
    sgtitle('Muscle activity by exosuit condition & walking condition (group mean \pm 95% CI, dots = subjects)', ...
        'FontWeight','bold');
end

function plot_reduction_bars(redA, redI, muscles, qA, qI, ttl)
    X = 1:4; w = 0.32; Nsub = size(redA,1);
    mA = mean(redA,1,'omitnan'); mI = mean(redI,1,'omitnan');
    cA = arrayfun(@(k) ci95(redA(:,k)), X);
    cI = arrayfun(@(k) ci95(redI(:,k)), X);

    figure('Name','Reduction vs No-Exo','Color','w','Position',[100 100 1150 620]); hold on;
    bar(X-0.17, mA, w, 'FaceColor',[0.30 0.75 0.93], 'DisplayName','Exo Active');
    bar(X+0.17, mI, w, 'FaceColor',[0.72 0.72 0.72], 'DisplayName','Exo Inactive');
    errorbar(X-0.17, mA, cA, 'k','linestyle','none','LineWidth',1.2,'CapSize',8,'HandleVisibility','off');
    errorbar(X+0.17, mI, cI, 'k','linestyle','none','LineWidth',1.2,'CapSize',8,'HandleVisibility','off');

    for k = X   % individual-subject dots
        jt = (rand(Nsub,1)-0.5)*0.12;
        scatter(k-0.17+jt, redA(:,k), 26, [0.10 0.32 0.42], 'filled', ...
            'MarkerFaceAlpha',0.6,'HandleVisibility','off');
        scatter(k+0.17+jt, redI(:,k), 26, [0.32 0.32 0.32], 'filled', ...
            'MarkerFaceAlpha',0.6,'HandleVisibility','off');
    end
    yline(0,'k-','HandleVisibility','off');

    for k = X   % significance stars on Active bars (FDR q)
        s = stars(qA(k));
        if ~isempty(s)
            text(k-0.17, mA(k)+cA(k)+2, s, 'HorizontalAlignment','center','FontSize',15);
        end
    end
    set(gca,'XTick',X,'XTickLabel',muscles);
    ylabel('% reduction vs No-Exo   (positive = support)');
    title(ttl); legend('Location','best'); grid on; box off;
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
