base_dir = '/Users/jahnav/Library/CloudStorage/Dropbox-ASU/Jahnav Rokalaboina/Exosuit & RL Project/New Exosuit/New_Testing/results';
subjects = {'Amir', 'Jeevan', 'Mason', 'Ruthvik'};
conditions = {'inc0spd0p8.mat', 'inc0spd1p2.mat', 'inc5spd0p8.mat', 'inc5spd1p2.mat'};
init_kineA = zeros(length(subjects), length(conditions));
for s = 1:length(subjects)
    for c = 1:length(conditions)
        file_path = fullfile(base_dir, subjects{s}, 'Final', conditions{c});
        if ~isfile(file_path)
            init_kineA(s,c)=NaN;
            continue;
        end
        data = load(file_path);
        mean_val = mean(data.all_kineA, 2, 'omitnan');
        valid_idx = find(~isnan(mean_val));
        if isempty(valid_idx)
            init_kineA(s,c)=NaN;
        else
            init_kineA(s,c)=mean_val(valid_idx(1));
        end
    end
end
disp('init_kineA:');
disp(init_kineA);
m_init = mean(init_kineA, 1, 'omitnan');
disp('m_init:');
disp(m_init);
disp('max overall:');
disp(max(m_init));
