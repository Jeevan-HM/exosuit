%% compare_trial_quality.m
% Run from a SINGLE participant folder. For every condition here that has TWO
% trials (…_trial1 and …_trial2), compare them on DATA-QUALITY grounds only
% (blind to EMG magnitude / to any exosuit effect) and recommend which to keep.
%
% Quality is judged on three magnitude-independent indicators, per muscle then
% averaged over VL/RF/BF/ST:
%   1) n_cycles      — usable strides collected (more = better coverage)
%   2) valid %       — fraction of strides that processed cleanly
%                       (not all-NaN, not flatlined/zero = no dropout)
%   3) consistency   — mean shape correlation of each stride to the trial's
%                       mean waveform (0–1). High = repeatable, low-noise signal.
% Composite = consistency * valid%  (0–1). The trial with the higher composite
% is recommended; if within TOL, prefer the one with more cycles.
%
% NOTE: none of these look at activation LEVEL, so the choice cannot bias your
% noexo-vs-active reduction.


clear; clc;
TOL = 0.02;                       % "comparable" threshold on the composite
muscles = {'VL', 'RF', 'BF', 'ST'};

root = fileparts(mfilename('fullpath'));
if isempty(root), root = pwd; end   % this participant's folder

files2 = dir(fullfile(root, '*_trial2.mat'));
if isempty(files2)
    error('No *_trial2.mat files found in %s', root);
end

[~, folder_name] = fileparts(root);
fprintf('="*80\n');
fprintf('TRIAL QUALITY COMPARISON (data-quality only) — %s\n', folder_name);
fprintf('="*80\n');

for f = 1:numel(files2)
    fpath2 = fullfile(root, files2(f).name);
    fpath1 = strrep(fpath2, 'trial2', 'trial1');
    if exist(fpath1, 'file') ~= 2
        fprintf('  (no trial1 match for %s — skipped)\n', files2(f).name);
        continue;
    end

    % Condition label = filename between 'Processed_' and '_trial1'
    [~, name1] = fileparts(fpath1);
    tok = regexp(name1, 'Processed_(.*)_trial1', 'tokens', 'once');
    if isempty(tok), label = name1; else, label = tok{1}; end

    q1 = trial_quality(fpath1, muscles);
    q2 = trial_quality(fpath2, muscles);

    if abs(q1.composite - q2.composite) < TOL
        % comparable overall → decide on the cleaner signal (higher consistency)
        if q1.consistency >= q2.consistency, pick = 1; else, pick = 2; end
        note = '(comparable → chose higher consistency)';
    elseif q1.composite > q2.composite
        pick = 1; note = '';
    else
        pick = 2; note = '';
    end

    fprintf('\n%s\n', label);
    fprintf('   %-14s  %8s  %8s\n', 'metric', 'trial1', 'trial2');
    fprintf('   %-14s  %8d  %8d\n', 'n_cycles',    q1.n_cycles,    q2.n_cycles);
    fprintf('   %-14s  %7.1f%%  %7.1f%%\n', 'valid',  100*q1.validfrac, 100*q2.validfrac);
    fprintf('   %-14s  %8.3f  %8.3f\n', 'consistency', q1.consistency, q2.consistency);
    fprintf('   %-14s  %8.3f  %8.3f\n', 'COMPOSITE',   q1.composite,   q2.composite);
    fprintf('   >>> USE TRIAL %d  %s\n', pick, note);
end

fprintf('\n="*80\nDone.\n');

%% ============================ LOCAL FUNCTION ============================
function q = trial_quality(fpath, muscles)
    d = load(fpath, 'emg_cycles', 'n_cycles');
    validfrac = nan(1,4); consist = nan(1,4);

    for k = 1:4
        X = cell2mat(d.emg_cycles.(muscles{k})');       % 1001 x n_cycles
        % A stride is "bad" if all-NaN (failed) or flatlined/zero (dropout)
        good = ~all(isnan(X), 1) & ~all(X == 0 | isnan(X), 1);
        Xv = X(:, good);
        validfrac(k) = size(Xv, 2) / max(size(X, 2), 1);

        if size(Xv, 2) >= 2
            mu  = mean(Xv, 2, 'omitnan');               % mean waveform
            % Pearson corr of each stride to the mean waveform (manual, no toolbox)
            Xc  = Xv - mean(Xv, 1);
            muc = mu - mean(mu);
            num = sum(Xc .* muc, 1);
            den = sqrt(sum(Xc.^2, 1) .* sum(muc.^2));
            r   = num ./ den;
            consist(k) = mean(r(isfinite(r)));
        end
    end

    q.n_cycles    = d.n_cycles;
    q.validfrac   = mean(validfrac, 'omitnan');
    q.consistency = mean(consist,   'omitnan');
    q.composite   = q.consistency * q.validfrac;
end
