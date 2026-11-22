% --- Configuration ---
%filename = 'Processed_inc0_spd0.8_active_rl_trial1.mat'; % Name of your target .mat file
clc; clear;

filename = 'Procvsdvsssed_inc5_spd0.8_noexo_trial1.mat';

% mvc_trial{1}.mvc_VL = 0.000027506719480932594;
% mvc_trial{1}.mvc_RF = 0.0001471910522412176*0.3; 
% mvc_trial{1}.mvc_BF = 0.00003703623363533903*0.3;
% mvc_trial{1}.mvc_ST = 1.575077217024475e-05*0.8;
% 1. Load the file
fileData = load(filename);

% 2. Divide EVERY 1001x1 array inside the cell arrays by 1.5
% The @(x) x / 1.5 tells MATLAB to take each cell's contents (x) and divide by 1.5.
% 'UniformOutput', false ensures the output stays packaged as a cell array.

fileData.emg_cycles.VL = cellfun(@(x) x / 1, fileData.emg_cycles.VL, 'UniformOutput', false);
fileData.emg_cycles.RF = cellfun(@(x) x / 0.3, fileData.emg_cycles.RF, 'UniformOutput', false);
fileData.emg_cycles.BF = cellfun(@(x) x / 0.3, fileData.emg_cycles.BF, 'UniformOutput', false);
fileData.emg_cycles.ST = cellfun(@(x) x / 0.8, fileData.emg_cycles.ST, 'UniformOutput', false);

% 3. Save it back
save(filename, '-struct', 'fileData');

disp('All N vectors in each cell array have been divided successfully.');