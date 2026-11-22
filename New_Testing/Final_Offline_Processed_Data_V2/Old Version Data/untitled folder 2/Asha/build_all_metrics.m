%% build_all_metrics.m
% AUTOMATED version of the manual compare_trials.m packaging step.
% Run from a participant folder AFTER you've eyeballed compare_trials.m and are
% happy with the MVC values. For each of the 4 walking conditions it:
%   1. loads noexo, inactive, and the BEST of the two active_rl trials
%      (best = higher data-quality composite, blind to EMG magnitude — same
%       criterion as compare_trial_quality.m),
%   2. computes the SAME per-stride metrics compare_trials.m packages
%      (per-stride-then-across-strides: whole-cycle mean, peak, iEMG, and both
%       functional-zone means), in canonical order {noexo, exoinactive, exoactive},
%   3. saves <subject>_inc<i>_spd<s>_metrics.mat for aggregate_metrics.m.
%
% Output files match compare_trials.m exactly, so aggregate_metrics.m reads them
% with no changes.

clear; clc;

% ===== SET MVC (per subject; keep identical to this folder's compare_trials.m) =====
mvc.mvc_VL = 0.00016898409141060113;
mvc.mvc_RF = 0.00011001793889878477;
mvc.mvc_BF = 0.000045232285276508225;
mvc.mvc_ST = 6.528830137311291e-05;


% ===== CONFIG =====
TOL        = 0.02;   % same "comparable" threshold as compare_trial_quality.m
walks      = {'inc0_spd0.8', 'inc0_spd1.2', 'inc5_spd0.8', 'inc5_spd1.2'};
muscles    = {'VL', 'RF', 'BF', 'ST'};
cond_names = {'noexo', 'exoinactive', 'exoactive'};
ctrl_tok   = {'noexo', 'inactive', 'active_rl'};   % filename controller per canonical condition

root = fileparts(mfilename('fullpath'));
if isempty(root), root = pwd; end
[~, subject] = fileparts(root);

fprintf('="*80\n');
fprintf('BUILD ALL METRICS — %s\n', subject);
fprintf('="*80\n');

for wi = 1:numel(walks)
    walk = walks{wi};

    % ----- pick one file per condition -----
    files = cell(1,3); active_note = '';
    ok = true;
    for c = 1:3
        d = dir(fullfile(root, sprintf('Processed_%s_%s_trial*.mat', walk, ctrl_tok{c})));
        if isempty(d)
            fprintf('  [%s] missing %s — skipping this walking condition.\n', walk, ctrl_tok{c});
            ok = false; break;
        end
        if c < 3 || numel(d) == 1
            files{c} = fullfile(root, d(1).name);
            if c == 3, active_note = sprintf('%s (only trial)', d(1).name); end
        else
            % active_rl with 2+ trials: IDENTICAL decision to compare_trial_quality.m
            % (highest composite; if within TOL of the best, prefer more cycles).
            nt = numel(d); comp = nan(1,nt); cons = nan(1,nt); fps = cell(1,nt);
            for j = 1:nt
                fps{j} = fullfile(root, d(j).name);
                qj = trial_quality(fps{j}, muscles);
                comp(j) = qj.composite; cons(j) = qj.consistency;
            end
            [~, bi] = max(comp);
            near = (max(comp) - comp) < TOL;         % trials comparable to the best
            if sum(near) > 1
                cand = find(near);
                [~, ii] = max(cons(cand)); bi = cand(ii);   % tie-break: higher consistency
            end
            files{c} = fps{bi}; active_note = d(bi).name;
        end
    end
    if ~ok, continue; end

    % ----- metadata -----
    incline = str2double(regexp(walk, 'inc(\d+)',     'tokens', 'once'));
    spd_tok = regexp(walk, 'spd([0-9.]+)', 'tokens', 'once');
    speed   = str2double(spd_tok{1});
    tag     = sprintf('%s_inc%d_spd%s', subject, incline, strrep(num2str(speed), '.', 'p'));

    % ----- compute metrics per condition (canonical order) -----
    metrics = struct();
    metrics.subject    = subject;
    metrics.incline    = incline;
    metrics.speed      = speed;
    metrics.conditions = cond_names;
    metrics.muscles    = muscles;
    metrics.zones      = {'ext', 'flex'};
    metrics.tag        = tag;
    metrics.active_trial_used = active_note;

    Z = nan(3,4);
    metrics.n_cycles        = nan(1,3);
    metrics.wholecycle_mean = Z; metrics.wholecycle_sd = Z;
    metrics.peak_mean       = Z; metrics.peak_sd       = Z;
    metrics.iemg_mean       = Z; metrics.iemg_sd       = Z;
    metrics.ext_zone_mean   = Z; metrics.ext_zone_sd   = Z;
    metrics.flex_zone_mean  = Z; metrics.flex_zone_sd  = Z;

    for c = 1:3
        s = per_condition_metrics(files{c}, mvc, muscles);
        metrics.n_cycles(c)          = s.n_cycles;
        metrics.wholecycle_mean(c,:) = s.wholecycle_mean; metrics.wholecycle_sd(c,:) = s.wholecycle_sd;
        metrics.peak_mean(c,:)       = s.peak_mean;       metrics.peak_sd(c,:)       = s.peak_sd;
        metrics.iemg_mean(c,:)       = s.iemg_mean;       metrics.iemg_sd(c,:)       = s.iemg_sd;
        metrics.ext_zone_mean(c,:)   = s.ext_zone_mean;   metrics.ext_zone_sd(c,:)   = s.ext_zone_sd;
        metrics.flex_zone_mean(c,:)  = s.flex_zone_mean;  metrics.flex_zone_sd(c,:)  = s.flex_zone_sd;
    end

    outfile = fullfile(root, [tag '_metrics.mat']);
    save(outfile, 'metrics');
    fprintf('\n[%s]  active trial chosen: %s\n', walk, active_note);
    fprintf('   cycles (noexo/inact/active): %d / %d / %d\n', metrics.n_cycles);
    fprintf('   saved: %s_metrics.mat\n', tag);
end

fprintf('\n="*80\nDone. Now run aggregate_metrics.m in Offline_Processed_Data.\n');

%% ============================ LOCAL FUNCTIONS ============================
function s = per_condition_metrics(fpath, mvc, muscles)
    d   = load(fpath, 'emg_cycles', 'pgc_emg', 'n_cycles');
    pgc = d.pgc_emg;
    idx_ext  = (pgc >= 13 & pgc < 37) | (pgc >= 68 & pgc <= 100);
    idx_flex = (pgc >= 0  & pgc < 13) | (pgc >= 37 & pgc < 68);
    mvcv = [mvc.mvc_VL, mvc.mvc_RF, mvc.mvc_BF, mvc.mvc_ST];

    s.n_cycles = d.n_cycles;
    for k = 1:4
        X = cell2mat(d.emg_cycles.(muscles{k})') ./ mvcv(k) * 100;   % 1001 x n_cycles
        cyc = mean(X, 1, 'omitnan');     % whole-cycle mean per stride
        pk  = max(X, [], 1, 'omitnan');  % peak per stride
        ie  = trapz(pgc, X, 1);          % iEMG per stride
        ez  = mean(X(idx_ext,  :), 1, 'omitnan');   % extension-zone mean per stride
        fz  = mean(X(idx_flex, :), 1, 'omitnan');   % flexion-zone mean per stride

        s.wholecycle_mean(k) = mean(cyc,'omitnan'); s.wholecycle_sd(k) = std(cyc,0,'omitnan');
        s.peak_mean(k)       = mean(pk,'omitnan');  s.peak_sd(k)       = std(pk,0,'omitnan');
        s.iemg_mean(k)       = mean(ie,'omitnan');  s.iemg_sd(k)       = std(ie,0,'omitnan');
        s.ext_zone_mean(k)   = mean(ez,'omitnan');  s.ext_zone_sd(k)   = std(ez,0,'omitnan');
        s.flex_zone_mean(k)  = mean(fz,'omitnan');  s.flex_zone_sd(k)  = std(fz,0,'omitnan');
    end
end

function q = trial_quality(fpath, muscles)
    % Data-quality composite (magnitude-independent): consistency * valid%.
    d = load(fpath, 'emg_cycles', 'n_cycles');
    validfrac = nan(1,4); consist = nan(1,4);
    for k = 1:4
        X = cell2mat(d.emg_cycles.(muscles{k})');
        good = ~all(isnan(X), 1) & ~all(X == 0 | isnan(X), 1);
        Xv = X(:, good);
        validfrac(k) = size(Xv,2) / max(size(X,2), 1);
        if size(Xv,2) >= 2
            mu  = mean(Xv, 2, 'omitnan');
            Xc  = Xv - mean(Xv, 1);
            muc = mu - mean(mu);
            num = sum(Xc .* muc, 1);
            den = sqrt(sum(Xc.^2, 1) .* sum(muc.^2));
            r   = num ./ den;
            consist(k) = mean(r(isfinite(r)));
        end
    end
    q.consistency = mean(consist, 'omitnan');
    q.composite   = q.consistency * mean(validfrac, 'omitnan');
end
