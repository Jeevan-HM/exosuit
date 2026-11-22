%% plot_wholecycle_controller_combined.m  (v2: paired "slope" format)
% One figure that replaces v2_L1_wholecycle and v2_controller_comparison.
% Three conditions per muscle, shown as absolute whole-cycle activity (% MVC):
%   Row (a): pooled over the 4 walking conditions   -> No-Exo | Inactive  | Active (RL)
%   Row (b): 0% grade, 1.2 m/s (heuristic tested)    -> No-Exo | Heuristic | RL
% Thin grey lines = individual participants (paired), coloured markers = group mean
% with 95% CI. Stars = Wilcoxon signed-rank on the % reduction vs No-Exo, FDR across
% the 4 muscles (same tests as aggregate_metrics_v2.m and controller_comparison.m).
%
% Row (b) in % MVC: the controller files are raw envelopes, so heuristic and RL are
% converted with  X_%MVC = NoExo_%MVC(0%/1.2 m/s, from *_metrics.mat) * X_raw/NoExo_raw.
% The ratio is MVC-invariant, so the % reductions are exactly those of controller_comparison.m.
%
% Put this file next to aggregate_metrics_v2.m / controller_comparison.m (Offline_Processed_Data).
% Neither script is modified. R2020a compatible.

clear; clc; close all;

muscles  = {'VL','RF','BF','ST'};
hasStats = (exist('signrank','file')==2) || license('test','Statistics_Toolbox');
COND_B   = 'inc0_spd1.2';  INC_B = 0;  SPD_B = 1.2;   % condition used for row (b)

% ---- style ----
FIG.font='Times New Roman'; FIG.fs=9;
FIG.cNoexo=[0.45 0.45 0.45]; FIG.cIna=[0.47 0.67 0.19]; FIG.cAct=[0.15 0.53 0.82]; FIG.cHeur=[0.85 0.50 0.15];
FIG.w=18; FIG.h=9;            % cm; full page width (figure*). Try FIG.w=8.8; FIG.h=9 for one column.
FIG.save=false; FIG.dir='paper_figures_v2'; FIG.name='v2_wholecycle_controller'; FIG.dpi=600;
set(groot,'defaultAxesFontName',FIG.font,'defaultTextFontName',FIG.font, ...
    'defaultLegendFontName',FIG.font,'defaultAxesFontSize',FIG.fs,'defaultAxesLineWidth',0.8);

this_dir=fileparts(mfilename('fullpath')); if isempty(this_dir), this_dir=pwd; end

%% ===================== LOAD *_metrics.mat (row a, and No-Exo %MVC for row b) =====================
files=dir(fullfile(this_dir,'**','*_metrics.mat'));
keep=arrayfun(@(x) strcmp(fileparts(x.folder),this_dir) && ~contains(x.folder,'Old Version Data'), files);
files=files(keep);
if isempty(files), error('No *_metrics.mat found directly under a subject folder of %s', this_dir); end

Subj={}; Spd=[]; Inc=[]; Mus={}; Cnd={}; WC=[];
for f=1:numel(files)
    S=load(fullfile(files(f).folder,files(f).name),'metrics'); if ~isfield(S,'metrics'), continue; end
    m=S.metrics; [~,sdir]=fileparts(files(f).folder);       % subject = folder name
    for c=1:3
        for k=1:4
            Subj{end+1,1}=sdir; Spd(end+1,1)=m.speed; Inc(end+1,1)=m.incline; %#ok<*AGROW>
            Mus{end+1,1}=muscles{k}; Cnd{end+1,1}=m.conditions{c};
            WC(end+1,1)=m.wholecycle_mean(c,k);
        end
    end
end
D=table(Subj,Spd,Inc,Mus,Cnd,WC);
subs=unique(D.Subj); Ns=numel(subs);

% ---- row (a): absolute %MVC pooled over walking conditions, and % reductions ----
condA={'noexo','exoinactive','exoactive'};
absA=nan(Ns,4,3);
for si=1:Ns
    for k=1:4
        for c=1:3
            sel=strcmp(D.Subj,subs{si})&strcmp(D.Mus,muscles{k})&strcmp(D.Cnd,condA{c});
            absA(si,k,c)=mean(D.WC(sel),'omitnan');
        end
    end
end
redA=reduction(absA);                         % Ns x 4 x 2 : (inactive, active) vs No-Exo
qA=nan(2,4);
for j=1:2
    p=arrayfun(@(k) signrank_safe(redA(:,k,j),hasStats),1:4); qA(j,:)=bh_fdr(p);
end

%% ===================== ROW (b): heuristic vs RL at 0% / 1.2 m/s =====================
absB=nan(Ns,4,3);   % No-Exo | Heuristic | RL, in %MVC
for si=1:Ns
    sd=fullfile(this_dir,subs{si});
    fno=fullfile(sd,['Processed_' COND_B '_noexo_trial1.mat']);
    fbl=fullfile(sd,['Processed_' COND_B '_baseline_trial1.mat']);
    d_rl=dir(fullfile(sd,['Processed_' COND_B '_active_rl_trial*.mat']));
    if exist(fno,'file')~=2 || exist(fbl,'file')~=2 || isempty(d_rl)
        warning('%s: missing a file for %s, skipping row (b).', subs{si}, COND_B); continue;
    end
    if numel(d_rl)==1
        frl=fullfile(sd,d_rl(1).name);
    else   % same magnitude-blind trial choice as controller_comparison.m
        qbest=-inf;
        for j=1:numel(d_rl)
            fp=fullfile(sd,d_rl(j).name); qq=trial_quality(fp,muscles);
            if qq>qbest, qbest=qq; frl=fp; end
        end
    end
    no=wholecycle(fno,muscles); bl=wholecycle(fbl,muscles); rl=wholecycle(frl,muscles);
    for k=1:4
        sel=strcmp(D.Subj,subs{si})&strcmp(D.Mus,muscles{k})&strcmp(D.Cnd,'noexo') ...
            &D.Inc==INC_B&abs(D.Spd-SPD_B)<1e-6;
        noMVC=mean(D.WC(sel),'omitnan');
        if isnan(noMVC) || isnan(no(k)) || no(k)==0, continue; end
        absB(si,k,:)=noMVC*[1, bl(k)/no(k), rl(k)/no(k)];
    end
end
redB=reduction(absB);                         % (heuristic, RL) vs No-Exo
qB=nan(2,4);
for j=1:2
    p=arrayfun(@(k) signrank_safe(redB(:,k,j),hasStats),1:4); qB(j,:)=bh_fdr(p);
end

%% ===================== FIGURE: 2 rows x 4 muscles =====================
hf=figure('Name',FIG.name,'Color','w','Units','centimeters','Position',[2 2 FIG.w FIG.h]);
figure(hf); tl=tiledlayout(2,4,'TileSpacing','compact','Padding','compact');
colA=[FIG.cNoexo; FIG.cIna;  FIG.cAct]; labA={'No-Exo','Inactive','Active'};
colB=[FIG.cNoexo; FIG.cHeur; FIG.cAct]; labB={'No-Exo','Heuristic','RL'};
ax=gobjects(2,4);
for k=1:4
    ax(1,k)=nexttile(tl,k);
    slope_panel(ax(1,k), squeeze(absA(:,k,:)), qA(:,k), colA, labA, FIG);
    title(ax(1,k),muscles{k},'FontWeight','bold','FontSize',FIG.fs+1);
    ax(2,k)=nexttile(tl,4+k);
    slope_panel(ax(2,k), squeeze(absB(:,k,:)), qB(:,k), colB, labB, FIG);
end
ylabel(ax(1,1),{'(a) All walking conditions','Activity (% MVC)'});
ylabel(ax(2,1),{'(b) 0% grade, 1.2 m/s','Activity (% MVC)'});
for k=1:4   % same y-range within each muscle column, starting at 0
    yt=max([ax(1,k).YLim(2) ax(2,k).YLim(2)]);
    ylim(ax(1,k),[0 yt]); ylim(ax(2,k),[0 yt]);
end

if FIG.save
    outdir=fullfile(this_dir,FIG.dir); if ~exist(outdir,'dir'), mkdir(outdir); end
    save_png(hf,fullfile(outdir,[FIG.name '.png']),FIG.dpi);
    fprintf('Figure exported to %s\n',fullfile(outdir,[FIG.name '.png']));
end

%% ===================== QUICK CHECK AGAINST THE PAPER NUMBERS =====================
fprintf('\nRow (a), pooled, N=%d   (%% reduction vs No-Exo)\n',sum(any(~isnan(absA(:,:,1)),2)));
for k=1:4
    fprintf('  %-3s Inactive %6.1f (q=%.3f) | Active %6.1f (q=%.3f)\n',muscles{k}, ...
        mean(redA(:,k,1),'omitnan'),qA(1,k),mean(redA(:,k,2),'omitnan'),qA(2,k));
end
fprintf('Row (b), %s, N=%d\n',COND_B,sum(any(~isnan(absB(:,:,1)),2)));
for k=1:4
    fprintf('  %-3s Heuristic %6.1f (q=%.3f) | RL %6.1f (q=%.3f)\n',muscles{k}, ...
        mean(redB(:,k,1),'omitnan'),qB(1,k),mean(redB(:,k,2),'omitnan'),qB(2,k));
end

%% ============================ LOCAL FUNCTIONS ============================
function slope_panel(ax, V, q, cols, labs, FIG)
    % V: Ns x 3 (%MVC). Paired lines per participant + mean +/- 95% CI per condition.
    hold(ax,'on'); X=1:3;
    for i=1:size(V,1)
        if all(isnan(V(i,:))), continue; end
        plot(ax,X,V(i,:),'-','Color',[0.80 0.80 0.80],'LineWidth',0.6);
        scatter(ax,X,V(i,:),8,[0.70 0.70 0.70],'filled');
    end
    m=mean(V,1,'omitnan'); c=arrayfun(@(j) ci95(V(:,j)),X);
    plot(ax,X,m,'-','Color',[0.15 0.15 0.15],'LineWidth',1.2);
    for j=X
        errorbar(ax,X(j),m(j),c(j),'o','Color',cols(j,:),'MarkerFaceColor',cols(j,:), ...
            'MarkerEdgeColor','none','MarkerSize',5.5,'LineWidth',1.3,'CapSize',4);
    end
    yl=ylim(ax); ytop=max([yl(2), max(V(:),[],'omitnan')]);
    for j=2:3   % stars: condition j vs No-Exo
        s=stars(q(j-1));
        if ~isempty(s), text(ax,X(j),ytop*1.06,s,'HorizontalAlignment','center','FontSize',FIG.fs+1); end
    end
    ylim(ax,[0 ytop*1.15]);
    set(ax,'XTick',X,'XTickLabel',labs,'XTickLabelRotation',30,'TickLength',[0 0]);
    xlim(ax,[0.6 3.4]); box(ax,'off');
end

function R=reduction(ABS)
    % ABS: Ns x 4 x 3 with column 1 = No-Exo. Returns Ns x 4 x 2 % reduction vs No-Exo.
    no=ABS(:,:,1); no(no==0)=NaN;
    R=cat(3,(no-ABS(:,:,2))./no*100,(no-ABS(:,:,3))./no*100);
end

function wc=wholecycle(fpath,muscles)
    d=load(fpath,'emg_cycles'); wc=nan(1,4);
    for k=1:4
        X=cell2mat(d.emg_cycles.(muscles{k})');
        wc(k)=mean(X(:),'omitnan');
    end
end

function q=trial_quality(fpath,muscles)
    d=load(fpath,'emg_cycles'); validfrac=nan(1,4); consist=nan(1,4);
    for k=1:4
        X=cell2mat(d.emg_cycles.(muscles{k})');
        good=~all(isnan(X),1) & ~all(X==0 | isnan(X),1);
        Xv=X(:,good); validfrac(k)=size(Xv,2)/max(size(X,2),1);
        if size(Xv,2)>=2
            mu=mean(Xv,2,'omitnan'); Xc=Xv-mean(Xv,1); muc=mu-mean(mu);
            num=sum(Xc.*muc,1); den=sqrt(sum(Xc.^2,1).*sum(muc.^2));
            r=num./den; consist(k)=mean(r(isfinite(r)));
        end
    end
    q=mean(consist,'omitnan')*mean(validfrac,'omitnan');
end

function c=ci95(x)
    x=x(~isnan(x)); n=numel(x); if n<2, c=0; return; end
    c=tcrit95(n-1)*std(x)/sqrt(n);
end
function p=signrank_safe(x,hasStats)
    x=x(~isnan(x)); if hasStats&&numel(x)>=2, p=signrank(x); else, p=NaN; end
end
function q=bh_fdr(p)
    p=p(:)'; m=numel(p); q=nan(1,m); ok=~isnan(p); pp=p(ok); mm=numel(pp);
    if mm==0, return; end
    [ps,ix]=sort(pp); qs=ps.*mm./(1:mm);
    for i=mm-1:-1:1, qs(i)=min(qs(i),qs(i+1)); end
    qv=nan(1,mm); qv(ix)=min(qs,1); q(ok)=qv;
end
function tc=tcrit95(df)
    if df<1, tc=NaN; return; end
    if exist('tinv','file')==2, tc=tinv(0.975,df); return; end
    tbl=[12.71 4.303 3.182 2.776 2.571 2.447 2.365 2.306 2.262 2.228];
    if df<=10, tc=tbl(df); elseif df<=20, tc=2.086; elseif df<=30, tc=2.042; else, tc=1.96; end
end
function s=stars(p)
    if isnan(p), s=''; elseif p<0.001, s='***'; elseif p<0.01, s='**'; elseif p<0.05, s='*'; else, s=''; end
end
function save_png(h,file,dpi)
    try, exportgraphics(h,file,'Resolution',dpi);
    catch
        set(h,'Units','centimeters'); pp=get(h,'Position');
        set(h,'PaperUnits','centimeters','PaperPositionMode','manual','PaperSize',[pp(3) pp(4)],'PaperPosition',[0 0 pp(3) pp(4)]);
        print(h,file,'-dpng',sprintf('-r%d',dpi));
    end
end
