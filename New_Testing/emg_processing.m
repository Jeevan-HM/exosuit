function [envelope_norm, pgc] = emg_processing(emg_raw, mvc_value)
% EMG_PROCESSING  Processes raw EMG samples for a single gait cycle.
%
%   [envelope_norm, pgc] = emg_processing(emg_raw, mvc_value)
%
%   Inputs:
%     emg_raw   - Raw EMG samples for one gait cycle (Nx1 vector), at 2000 Hz
%     mvc_value - MVC scalar for this muscle (used for normalization)
%
%   Outputs:
%     envelope_norm - MVC-normalized EMG envelope, resampled to 1000 points (1001x1)
%     pgc           - Gait cycle axis, 0:0.1:100 (1001x1)
%
%   Algorithm matches nogrf_gaittiming.py emg_processing():
%     1. Bandpass filter: 20-450 Hz, 4th order Butterworth
%     2. Rolling RMS envelope via Simpson's rule integration (window=0.25s)
%     3. Linear interpolation to 1ms grid
%     4. Spline resample to 1001 points (0-100% gait cycle)
%     5. Normalize by MVC

    fs      = 2000;
    lowcut  = 100;
    highcut = 400;
    order   = 4;
    window  = 0.25;   % seconds
    method  = 2;      % downsampling factor used in Simpson's rule

    emg_raw = emg_raw(:);  % ensure column vector

    % --- Step 1: Bandpass Filter ---
    [b, a]       = butter(order, [lowcut highcut] / (fs/2), 'bandpass');
    emg_filtered = filtfilt(b, a, double(emg_raw));  % zero-phase (matches lfilter intent)

    % --- Step 2: Rolling RMS via Simpson's Rule (matching Python exactly) ---
    emg_to_process  = emg_filtered;
    integral_window = round(window * fs / method);
    signallength    = length(emg_to_process);
    h               = method / fs;   % = 0.001

    n_half = ceil(signallength / 2);
    I      = zeros(n_half, 1);

    for ii = 1 : floor(signallength/2 - 1)
        idx = ii * 2;  % MATLAB is 1-indexed; mimics Python's a*2
        % Python: emg[a*2-1], emg[a*2], emg[a*2+1]  (0-indexed)
        %       = emg[idx-1],  emg[idx],  emg[idx+1] (1-indexed MATLAB)
        if idx >= 2 && idx + 1 <= signallength
            I(ii) = (h/3) * (emg_to_process(idx-1)^2 + ...
                             4 * emg_to_process(idx)^2 + ...
                             emg_to_process(idx+1)^2);
        end
    end

    cuml    = zeros(n_half, 1);
    RMS_env = zeros(n_half, 1);
    cuml(1) = I(1);
    if cuml(1) >= 0
        RMS_env(1) = sqrt(cuml(1) / h);
    end

    % Build-up phase
    for ii = 2 : min(integral_window, n_half)
        cuml(ii)    = cuml(ii-1) + I(ii);
        denom       = (ii-1) * h;
        if denom > 0
            RMS_env(ii) = sqrt(max(cuml(ii), 0) / denom);
        end
    end

    % Sliding window phase
    for ii = integral_window + 1 : n_half
        cuml(ii)    = cuml(ii-1) + I(ii) - I(ii - integral_window);
        if cuml(ii) >= 0
            RMS_env(ii) = sqrt(cuml(ii) / window);
        end
    end

    % --- Step 3: Interpolate to 1 ms grid ---
    time_vect_ms = (0.002 : 0.002 : 0.002 * n_half) * 1000;  % in ms
    time_vect_ms = round(time_vect_ms);
    n_pts        = time_vect_ms(end);
    y            = zeros(n_pts, 1);

    for ii = 1 : length(time_vect_ms) - 1
        t1     = time_vect_ms(ii) + 1;
        t2     = time_vect_ms(ii + 1);
        if t1 > t2 || t1 < 1 || t2 > n_pts
            continue
        end
        lambda = (RMS_env(ii+1) - RMS_env(ii)) / (time_vect_ms(ii+1) - time_vect_ms(ii));
        t_span = t1 : t2;
        y(t1:t2) = RMS_env(ii) + lambda * (t_span - time_vect_ms(ii))';
    end
    RMS_interp = y;

    % --- Step 4: Spline resample to 1001 points (0-100% gait cycle) ---
    n_interp = length(RMS_interp);
    if n_interp < 2
        envelope_norm = zeros(1001, 1);
        pgc           = linspace(0, 100, 1001)';
        return;
    end

    x_in  = linspace(0, 100, n_interp);
    pgc   = linspace(0, 100, 1001)';
    RMS_pgc = interp1(x_in, RMS_interp, pgc, 'spline');

    % --- Step 5: Normalize by MVC ---
    if mvc_value > 0
        envelope_norm = RMS_pgc / mvc_value;
    else
        envelope_norm = RMS_pgc;
        warning('emg_processing: mvc_value is 0, skipping normalization.');
    end

end
