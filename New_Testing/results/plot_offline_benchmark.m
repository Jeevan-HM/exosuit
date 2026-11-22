%% plot_offline_benchmark.m
% Offline imitation-learning convergence: previous DHDP actor-critic vs the
% current TD-regularized (TDR) actor-critic. Reads new_device_BENCH.csv
% (Episode number, training Episode cost, Algorithm) and plots the two
% convergence curves so the paper can justify choosing TDR (faster, smoother,
% lower final cost).
%
% Style matches the other paper figures (Times New Roman, physical cm sizing,
% R2020a-safe PNG export via save_png fallback).

clear; clc; close all;

% ---- style ----
FIG.font='Times New Roman'; FIG.fs=13; FIG.lw=2;
FIG.cDHDP=[0.70 0.30 0.30];    % previous DHDP  (muted red)
FIG.cTDR =[0.15 0.53 0.82];    % current TDR    (blue, matches RL elsewhere)
FIG.save=true; FIG.name='offline_benchmark_TDR_vs_DHDP'; FIG.fmt='png'; FIG.dpi=600;
FIG.smoothW=9;                 % moving-average window for the trend line
set(groot,'defaultAxesFontName',FIG.font,'defaultTextFontName',FIG.font, ...
    'defaultLegendFontName',FIG.font,'defaultAxesFontSize',FIG.fs,'defaultAxesLineWidth',1);

this_dir=fileparts(mfilename('fullpath')); if isempty(this_dir), this_dir=pwd; end
csv=fullfile(this_dir,'new_device_BENCH.csv');
T=readtable(csv);
% normalize column names (readtable mangles spaces)
T.Properties.VariableNames = {'Episode','Cost','Algo'};

algos = {'DHDP','TDR'};
cols  = [FIG.cDHDP; FIG.cTDR];
labs  = {'DHDP (previous)','TDR (proposed)'};

% ---- common-scale normalization ----
% Both algorithms optimize the SAME offline imitation objective, so their costs
% share one scale. We divide BOTH curves by a single reference = the DHDP
% episode-0 cost, so the axis reads ~1 at the start (DHDP starts at exactly 1)
% while the true relative gap between the two algorithms is preserved.
mD = strcmp(T.Algo,'DHDP');
[~,ixD] = sort(T.Episode(mD)); cD = T.Cost(mD); cD = cD(ixD);
SCALE = cD(1);                          % DHDP cost at episode 0 (~7.63)
T.Cost = T.Cost / SCALE;                % normalize both algorithms by the same factor

hf=figure('Name',FIG.name,'Color','w','Units','centimeters','Position',[2 2 9 7]); hold on;

hLeg=gobjects(1,numel(algos));
for a=1:numel(algos)
    m = strcmp(T.Algo,algos{a});
    ep = T.Episode(m); c = T.Cost(m);
    [ep,ix]=sort(ep); c=c(ix);
    cs = movmean(c,FIG.smoothW);                 % smoothed trend
    % raw trace, faint
    plot(ep,c,'-','Color',[cols(a,:) 0.18],'LineWidth',0.8,'HandleVisibility','off');
    % smoothed trend, bold (this is the legend handle)
    hLeg(a)=plot(ep,cs,'-','Color',cols(a,:),'LineWidth',FIG.lw,'DisplayName',labs{a});
end

xlabel('Training episode'); ylabel('Normalized imitation cost');
xlim([0 max(T.Episode)]); ylim([0 inf]); box off;
grid on; set(gca,'GridColor',[0.5 0.5 0.5],'GridAlpha',0.25,'Layer','bottom');
legend(hLeg,'Location','northeast','Box','off');

% ---- console summary (final-cost comparison, last 20 episodes) ----
fprintf('\n>>> OFFLINE BENCHMARK SUMMARY >>>\n');
tailN=20;
for a=1:numel(algos)
    m=strcmp(T.Algo,algos{a}); c=T.Cost(m); ep=T.Episode(m);
    [~,ix]=sort(ep); c=c(ix);
    fprintf('  %-14s  final cost (last %d ep) = %.2f +/- %.2f ; peak = %.2f\n', ...
        labs{a}, tailN, mean(c(end-tailN+1:end)), std(c(end-tailN+1:end)), max(c));
end
fprintf('<<< COPY TO HERE <<<\n\n');

% ---- export ----
if FIG.save
    outfile=fullfile(this_dir,[FIG.name '.' FIG.fmt]);
    save_png(hf,outfile,FIG.dpi);
    fprintf('Saved figure: %s\n', outfile);
end

% ======================= helpers =======================
function save_png(h,file,dpi)
    try, exportgraphics(h,file,'Resolution',dpi);
    catch
        set(h,'Units','centimeters'); p=get(h,'Position');
        set(h,'PaperUnits','centimeters','PaperPositionMode','manual', ...
            'PaperSize',[p(3) p(4)],'PaperPosition',[0 0 p(3) p(4)]);
        print(h,file,'-dpng',sprintf('-r%d',dpi));
    end
end
