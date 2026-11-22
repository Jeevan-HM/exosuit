% --- Configuration ---
%filename = 'Processed_inc0_spd0.8_active_rl_trial1.mat'; % Name of your target .mat file
clc; clear;

filename = 'Procvdsessed_inc5_spd0.8_inactive_trial1.mat';

% 1. Load the file
fileData = load(filename);

% 2. Divide EVERY 1001x1 array inside the cell arrays by 1.5
% The @(x) x / 1.5 tells MATLAB to take each cell's contents (x) and divide by 1.5.
% 'UniformOutput', false ensures the output stays packaged as a cell array.

% mvc_trial{1}.mvc_VL = 0.0001902291492894007*0.15;
% mvc_trial{1}.mvc_RF = 0.00007820764613724852*0.5;
% mvc_trial{1}.mvc_BF = 0.00017779599376172066*0.7;
% mvc_trial{1}.mvc_ST = 3.1409063921334667e-05;

% Trial 2 MVC values (set to [] to load from .mat file)
% mvc_trial{2}.mvc_VL = 0.0001902291492894007*0.4;
% mvc_trial{2}.mvc_RF = 0.00007820764613724852*0.6;
% mvc_trial{2}.mvc_BF = 0.00017779599376172066*0.6;
% mvc_trial{2}.mvc_ST = 3.1409063921334667e-05*0.6;

fileData.emg_cycles.VL = cellfun(@(x) x / 0.4, fileData.emg_cycles.VL, 'UniformOutput', false);
fileData.emg_cycles.RF = cellfun(@(x) x / 0.6, fileData.emg_cycles.RF, 'UniformOutput', false);
fileData.emg_cycles.BF = cellfun(@(x) x / 0.6, fileData.emg_cycles.BF, 'UniformOutput', false);
fileData.emg_cycles.ST = cellfun(@(x) x / 0.6, fileData.emg_cycles.ST, 'UniformOutput', false);

% 3. Save it back
save(filename, '-struct', 'fileData');

disp('All N vectors in each cell array have been divided successfully.');