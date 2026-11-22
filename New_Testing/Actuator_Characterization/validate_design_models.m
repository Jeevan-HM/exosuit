%% validate_design_models.m
% Checks the torque and inflation/deflation-time models used in the actuator
% optimization WITHOUT new experiments. It only needs the numbers you already
% have: the five design configurations (Table III), their measured torque and
% times (data behind the "performance" figure), and the measured values of
% the two optimized actuators (data behind the "validation" figure).
%
% What it does
%   1. Torque: physics-motivated model T = a*A + b (virtual work: at fixed
%      pressure and moment arm, torque scales with pressurized area).
%   2. Time:   physics-motivated model t = t0 + k*V, where V is the chamber
%      volume computed from the Table III geometry (lumped pneumatic chamber:
%      at a given flow rate, fill/empty time grows with volume; t0 = valve
%      delay + tubing). Compared against the current empirical quadratic in A.
%   3. Leave-one-out cross-validation (LOO) on the five designs: each design
%      is predicted from a model fitted to the other four.
%   4. Out-of-sample check: predicts the optimized actuators (not used in
%      any fit) and reports the % error.
%   5. Optional: if the valve sonic conductance C (datasheet) is entered, the
%      a-priori slope k predicted by the chamber model is compared with the
%      fitted slope.
%
% >>> Fill in the MEASURED values marked "FILL" below (NaN = not entered). <<<

clear; clc;

%% ===== TABLE III GEOMETRY (from the paper) =====
A      = [642 1140 1787 2569 3504];        % cross-sectional area (mm^2)
F.Lup  = [364 379 394 409 424];            % SIFA upper fabric length (mm)
F.Ltot = [320 320 320 320 320];            % SIFA total length (mm)
F.Lrig = [114 119 123 128 133];            % SIFA rigid length (mm)
E.Ltot = [320 320 320 320 320];            % SIEA total length (mm)
E.Lrig = [144 142 140 138 136];            % SIEA rigid length (mm)

%% ===== MEASURED PERFORMANCE OF THE FIVE DESIGNS (FILL) =====
% mean values per design, same order as A. Torque in N m, times in ms.
F.T    = nan(1,5);   % FILL: SIFA torque
F.tinf = nan(1,5);   % FILL: SIFA inflation time
F.tdef = nan(1,5);   % FILL: SIFA deflation time
E.T    = nan(1,5);   % FILL: SIEA torque
E.tinf = nan(1,5);   % FILL: SIEA inflation time
E.tdef = nan(1,5);   % FILL: SIEA deflation time

%% ===== OPTIMIZED ACTUATORS (held out, FILL measured values) =====
F.Aopt = 1294;  F.opt = struct('T', NaN, 'tinf', NaN, 'tdef', NaN);   % FILL
E.Aopt = 941;   E.opt = struct('T', NaN, 'tinf', NaN, 'tdef', NaN);   % FILL

%% ===== OPTIONAL: valve data for an a-priori time slope =====
VALVE_C  = NaN;      % sonic conductance, dm^3/(s*bar) from the valve datasheet (NaN = skip)
P_SUPPLY = 270;      % supply pressure (kPa gauge)
P_TARGET = 69;       % target pressure (kPa gauge)
P_ATM    = 101.325;  % kPa

%% ===== CHAMBER VOLUMES FROM GEOMETRY =====
% SIEA: straight chamber, active length = Ltot - Lrig
% SIFA: bending chamber, active length taken as the mean of the upper
%       (Lup) and lower (Ltot) fabric lengths minus the rigid segment
F.Lact = (F.Lup + F.Ltot)/2 - F.Lrig;
E.Lact = E.Ltot - E.Lrig;
F.V = A .* F.Lact;  E.V = A .* E.Lact;              % mm^3
% geometry of the optimized designs: Table III parameters are linear in sqrt(A)
F.Voptf = @(a) a * ((interp1(sqrt(A), F.Lup, sqrt(a), 'linear', 'extrap') + 320)/2 ...
                    - interp1(sqrt(A), F.Lrig, sqrt(a), 'linear', 'extrap'));
E.Voptf = @(a) a * (320 - interp1(sqrt(A), E.Lrig, sqrt(a), 'linear', 'extrap'));

fprintf('Chamber volume from geometry (cm^3):\n');
fprintf('  A (mm^2):  %s\n', sprintf('%8.0f', A));
fprintf('  SIFA V  :  %s   | optimized (A=%d): %.1f\n', sprintf('%8.1f', F.V/1e3), F.Aopt, F.Voptf(F.Aopt)/1e3);
fprintf('  SIEA V  :  %s   | optimized (A=%d): %.1f\n', sprintf('%8.1f', E.V/1e3), E.Aopt, E.Voptf(E.Aopt)/1e3);

%% ===== RUN CHECKS =====
acts = {'SIFA (flexion)', F; 'SIEA (extension)', E};
for n = 1:2
    [name, S] = acts{n, :};
    fprintf('\n==================== %s ====================\n', name);
    Vopt = S.Voptf(S.Aopt);

    % ---- torque: linear in A ----
    check_model('Torque, T = a*A + b', A, S.T, @(x) [x(:) ones(numel(x),1)], S.Aopt, S.opt.T, 'N m');

    % ---- times: physics (linear in V) vs empirical (quadratic in A) ----
    for q = {'tinf', 'tdef'}
        f = q{1};  y = S.(f);  yopt = S.opt.(f);
        lbl = strrep(strrep(f, 'tinf', 'Inflation time'), 'tdef', 'Deflation time');
        check_model([lbl ', physics t = t0 + k*V'], S.V, y, @(x) [x(:) ones(numel(x),1)], Vopt, yopt, 'ms');
        check_model([lbl ', empirical t = a*A^2 + b*A + c'], A, y, @(x) [x(:).^2 x(:) ones(numel(x),1)], S.Aopt, yopt, 'ms');
    end

    % ---- optional a-priori inflation slope from the valve datasheet ----
    if ~isnan(VALVE_C) && all(~isnan(S.tinf))
        C  = VALVE_C * 1e-3 / 1e5;                 % dm^3/(s bar) -> m^3/(s Pa)
        Ps = (P_SUPPLY + P_ATM) * 1e3;  dP = P_TARGET * 1e3;  P0 = P_ATM * 1e3;
        k_iso = dP / (C * P0 * Ps) * 1e3 / 1e9;    % ms per mm^3 (isothermal filling)
        k_adi = k_iso / 1.4;                       % adiabatic filling
        p = polyfit(S.V, S.tinf, 1);
        fprintf('  A-priori inflation slope from valve C: %.3g to %.3g ms/cm^3 | fitted: %.3g ms/cm^3\n', ...
                k_adi*1e3, k_iso*1e3, p(1)*1e3);
    end
end
fprintf('\nDone.\n');

%% ======================= helper =======================
function check_model(label, x, y, X, xopt, yopt, unit)
    fprintf('\n  %s\n', label);
    if any(isnan(y)), fprintf('    (measured values not entered - skipped)\n'); return; end
    D = X(x);  b = D \ y(:);  yhat = D * b;
    r2 = 1 - sum((y(:) - yhat).^2) / sum((y(:) - mean(y)).^2);
    % leave-one-out cross-validation
    e = nan(size(y));
    for i = 1:numel(y)
        m = true(size(y)); m(i) = false;
        bi = X(x(m)) \ y(m)';
        e(i) = X(x(i)) * bi - y(i);
    end
    fprintf('    fit R^2 = %.3f | LOO RMSE = %.2f %s | LOO mean abs error = %.1f %%\n', ...
            r2, sqrt(mean(e.^2)), unit, 100 * mean(abs(e) ./ abs(y)));
    ypred = X(xopt) * b;
    if isnan(yopt)
        fprintf('    optimized design: predicted %.2f %s (measured value not entered)\n', ypred, unit);
    else
        fprintf('    optimized design: predicted %.2f, measured %.2f %s -> error %.1f %%\n', ...
                ypred, yopt, unit, 100 * (ypred - yopt) / yopt);
    end
end
