% --- Configuration ---
%filename = 'Processed_inc0_spd0.8_active_rl_trial1.mat'; % Name of your target .mat file
clc; clear;

filename = 'Procesvsdvsed_inc0_spd0.8_inactive_trial1.mat';


% mvc_trial{1}.mvc_VL = 0.000112853892754091678*0.7; 
% mvc_trial{1}.mvc_RF = 0.000112967051584963717*0.7;  
% mvc_trial{1}.mvc_BF = 0.00019127893450096795*0.7; 
% mvc_trial{1}.mvc_ST = 0.00004448378860487733; 
% 
% % Trial 2 MVC values (set to [] to load from .mat file)
% 
% mvc_trial{2}.mvc_VL = 0.000112853892754091678; 
% mvc_trial{2}.mvc_RF = 0.000112967051584963717;  
% mvc_trial{2}.mvc_BF = 0.00019127893450096795; 
% mvc_trial{2}.mvc_ST = 0.00004448378860487733*10; 
% 1. Load the file


% Trial 1 MVC values (set to [] to load from .mat file)

%inc0spd1.2
% mvc_trial{1}.mvc_VL = 0.000112853892754091678*0.2; 
% mvc_trial{1}.mvc_RF = 0.000112967051584963717*0.2;  
% mvc_trial{1}.mvc_BF = 0.00019127893450096795*0.5; 
% mvc_trial{1}.mvc_ST = 0.00004448378860487733*0.7; 
% 
% % Trial 2 MVC values (set to [] to load from .mat file)
% 
% mvc_trial{2}.mvc_VL = 0.000112853892754091678; 
% mvc_trial{2}.mvc_RF = 0.000112967051584963717;  
% mvc_trial{2}.mvc_BF = 0.00019127893450096795; 
% mvc_trial{2}.mvc_ST = 0.00004448378860487733*0.5; 
% 
%inc0spd0.8
% mvc_trial{1}.mvc_VL = 0.000112853892754091678*0.1; 
% mvc_trial{1}.mvc_RF = 0.000112967051584963717*0.2;  
% mvc_trial{1}.mvc_BF = 0.00019127893450096795*0.2; 
% mvc_trial{1}.mvc_ST = 0.00004448378860487733*0.6; 
% 
% % Trial 2 MVC values (set to [] to load from .mat file)
% 
% mvc_trial{2}.mvc_VL = 0.000112853892754091678; 
% mvc_trial{2}.mvc_RF = 0.000112967051584963717;  
% mvc_trial{2}.mvc_BF = 0.00019127893450096795; 
% mvc_trial{2}.mvc_ST = 0.00004448378860487733*0.5; 

fileData = load(filename);

% 2. Divide EVERY 1001x1 array inside the cell arrays by 1.5
% The @(x) x / 1.5 tells MATLAB to take each cell's contents (x) and divide by 1.5.
% 'UniformOutput', false ensures the output stays packaged as a cell array.

fileData.emg_cycles.VL = cellfun(@(x) x / 1, fileData.emg_cycles.VL, 'UniformOutput', false);
fileData.emg_cycles.RF = cellfun(@(x) x / 1, fileData.emg_cycles.RF, 'UniformOutput', false);
fileData.emg_cycles.BF = cellfun(@(x) x / 1, fileData.emg_cycles.BF, 'UniformOutput', false);
fileData.emg_cycles.ST = cellfun(@(x) x / 0.5, fileData.emg_cycles.ST, 'UniformOutput', false);

% 3. Save it back
save(filename, '-struct', 'fileData');

disp('All N vectors in each cell array have been divided successfully.');