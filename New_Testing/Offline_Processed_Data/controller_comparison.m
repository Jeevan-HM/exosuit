%% controller_comparison.m
% Heuristic (baseline) vs RL vs No-Exo at the single condition where the
% heuristic controller was tested: inc0 / spd1.2 (0% grade, 1.2 m/s).
%
% Metric: whole-cycle mean EMG reduction relative to No-Exo. This ratio is
% INVARIANT to MVC normalization, so raw processed envelopes are used directly
% (no per-subject MVC needed). Positive = less muscle activity than No-Exo.
%
% For the RL condition (two trials) the higher-quality trial is chosen with the
% same magnitude-blind criterion (stride-to-stride consistency x clean-stride
% fraction) used elsewhere. Outputs a comparison figure + copy-pasteable report.

clear; clc; close all;

COND    = 'inc0_spd1.2';                 % 0% grade, 1.2 m/s
muscles = {'VL','RF','BF','ST'};
hasStats = (exist('signrank','file')==2) || license('test','Statistics_Toolbox');

% ---- style ----
FIG.font='Times New Roman'; FIG.fs=13; FIG.lw=2; FIG.mk=55;
FIG.cHeur=[0.85 0.50 0.15]; FIG.cRL=[0.15 0.53 0.82];   % heuristic orange, RL blue
FIG.save=false; FIG.dir='paper_figures_v2'; FIG.fmt='png'; FIG.dpi=600;
set(groot,'defaultAxesFontName',FIG.font,'defaultTextFontName',FIG.font, ...
    'defaultLegendFontName',FIG.font,'defaultAxesFontSize',FIG.fs,'defaultAxesLineWidth',1);

this_dir=fileparts(mfilename('fullpath')); if isempty(this_dir), this_dir=pwd; end

% ---- auto-detect subjects that have the baseline file (direct subject folders) ----
bf=dir(fullfile(this_dir,'*',['Processed_' COND '_baseline_trial1.mat']));
subs={};
for i=1:numel(bf)
    if ~strcmp(fileparts(bf(i).folder),this_dir) || contains(bf(i).folder,'Old Version Data'), continue; end
    [~,sn]=fileparts(bf(i).folder); subs{end+1}=sn; %#ok<SAGROW>
end
subs=unique(subs); Ns=numel(subs);
if Ns==0, error('No baseline files found for condition %s under %s', COND, this_dir); end
fprintf('Controller comparison at %s: %d participants\n', COND, Ns);

%% ===== BUILD REDUCTIONS =====
redH=nan(Ns,4); redRL=nan(Ns,4); rl_used=cell(Ns,1);
for si=1:Ns
    sd=fullfile(this_dir,subs{si});
    fno=fullfile(sd,['Processed_' COND '_noexo_trial1.mat']);
    fbl=fullfile(sd,['Processed_' COND '_baseline_trial1.mat']);
    d_rl=dir(fullfile(sd,['Processed_' COND '_active_rl_trial*.mat']));
    if exist(fno,'file')~=2 || exist(fbl,'file')~=2 || isempty(d_rl)
        warning('%s: missing a file for %s, skipping.', subs{si}, COND); continue;
    end
    % choose best RL trial
    if numel(d_rl)==1
        frl=fullfile(sd,d_rl(1).name); rl_used{si}=d_rl(1).name;
    else
        qbest=-inf;
        for j=1:numel(d_rl)
            fp=fullfile(sd,d_rl(j).name); q=trial_quality(fp,muscles);
            if q>qbest, qbest=q; frl=fp; rl_used{si}=d_rl(j).name; end
        end
    end
    no=wholecycle(fno,muscles); bl=wholecycle(fbl,muscles); rl=wholecycle(frl,muscles);
    ok = no~=0 & ~isnan(no);
    redH(si,ok)=(no(ok)-bl(ok))./no(ok)*100;
    redRL(si,ok)=(no(ok)-rl(ok))./no(ok)*100;
end

%% ===== STATS =====
alpha=0.05;
pH=nan(1,4); pRL=nan(1,4); pD=nan(1,4);
dzH=nan(1,4); dzRL=nan(1,4);
for k=1:4
    h=redH(:,k); r=redRL(:,k);
    pH(k)=signrank_safe(h,hasStats); pRL(k)=signrank_safe(r,hasStats);
    both=isfinite(h)&isfinite(r);
    pD(k)=signrank_safe(r(both)-h(both),hasStats);   % RL vs heuristic (paired)
    dzH(k)=effect_dz(h); dzRL(k)=effect_dz(r);
end
qH=bh_fdr(pH); qRL=bh_fdr(pRL); qD=bh_fdr(pD);
Ho=mean(redH,2,'omitnan'); Ro=mean(redRL,2,'omitnan');   % per-subject overall
bothO=isfinite(Ho)&isfinite(Ro);
pD_all=signrank_safe(Ro(bothO)-Ho(bothO),hasStats);

%% ===== FIGURE =====
X=1:4; off=0.17;
hf=figure('Name','v2_controller_comparison','Color','w','Units','centimeters','Position',[2 2 9.5 8]); hold on;
yline(0,'-','Color',[0.75 0.75 0.75],'LineWidth',1,'HandleVisibility','off');
mH=mean(redH,1,'omitnan'); mR=mean(redRL,1,'omitnan');
cH=arrayfun(@(k) ci95(redH(:,k)),X); cR=arrayfun(@(k) ci95(redRL(:,k)),X);
for k=X
    jt=(rand(Ns,1)-0.5)*0.10;
    scatter((k-off)+jt,redH(:,k),FIG.mk*0.3,FIG.cHeur,'filled','MarkerFaceAlpha',0.25,'HandleVisibility','off');
    scatter((k+off)+jt,redRL(:,k),FIG.mk*0.3,FIG.cRL,'filled','MarkerFaceAlpha',0.25,'HandleVisibility','off');
end
errorbar(X-off,mH,cH,'^','Color',FIG.cHeur,'MarkerFaceColor',FIG.cHeur,'MarkerSize',6,'LineWidth',FIG.lw-0.4,'CapSize',5,'DisplayName','Heuristic');
errorbar(X+off,mR,cR,'o','Color',FIG.cRL,'MarkerFaceColor',FIG.cRL,'MarkerSize',6,'LineWidth',FIG.lw-0.4,'CapSize',5,'DisplayName','RL');
for k=X   % stars = each controller vs No-Exo (FDR)
    sh=stars(qH(k)); if ~isempty(sh), text(k-off,mH(k)+cH(k)+4,sh,'HorizontalAlignment','center','FontSize',FIG.fs); end
    sr=stars(qRL(k)); if ~isempty(sr), text(k+off,mR(k)+cR(k)+4,sr,'HorizontalAlignment','center','FontSize',FIG.fs); end
end
set(gca,'XTick',X,'XTickLabel',muscles); xlim([0.5 4.5]);
ylabel('Reduction vs No-Exo (%)');
legend('Location','northoutside','Orientation','horizontal','Box','off'); box off;

if FIG.save
    outdir=fullfile(this_dir,FIG.dir); if ~exist(outdir,'dir'), mkdir(outdir); end
    save_png(hf,fullfile(outdir,'v2_controller_comparison.png'),FIG.dpi);
    fprintf('Figure exported to %s\n',fullfile(outdir,'v2_controller_comparison.png'));
end

%% ===== COPY-PASTEABLE REPORT =====
R=sprintf('\n>>> COPY FROM HERE - CONTROLLER COMPARISON (heuristic vs RL) >>>\n');
R=[R sprintf('Condition: %s (0%% grade, 1.2 m/s). N=%d participants.\n', COND, Ns)];
R=[R sprintf('Whole-cycle reduction vs No-Exo (%%, positive = less activity); MVC-invariant.\n')];
R=[R sprintf('Stats: Wilcoxon signed-rank; q = Benjamini-Hochberg FDR (across 4 muscles). alpha=%.2f.\n\n',alpha)];
R=[R sprintf('%-4s | %-22s | %-22s | %-16s\n','Musc','Heuristic vs No-Exo','RL vs No-Exo','RL vs Heuristic')];
R=[R sprintf('%-4s | %7s %5s %5s %-4s | %7s %5s %5s %-4s | %7s %5s\n','', ...
    'mean%','dz','q','','mean%','dz','q','','diff%','q')];
for k=1:4
    R=[R sprintf('%-4s | %6.1f %5.2f %5.3f %-4s | %6.1f %5.2f %5.3f %-4s | %6.1f %5.3f %s\n', muscles{k}, ...
        mean(redH(:,k),'omitnan'),dzH(k),qH(k),sig_star(qH(k)), ...
        mean(redRL(:,k),'omitnan'),dzRL(k),qRL(k),sig_star(qRL(k)), ...
        mean(redRL(:,k)-redH(:,k),'omitnan'),qD(k),sig_star(qD(k)))];
end
R=[R sprintf('\nOverall (avg of 4 muscles): Heuristic %.1f%%, RL %.1f%%; RL-vs-heuristic p=%.3f %s\n', ...
    mean(Ho,'omitnan'), mean(Ro,'omitnan'), pD_all, sig_star(pD_all))];
R=[R sprintf('RL trial used per subject:\n')];
for si=1:Ns, if ~isempty(rl_used{si}), R=[R sprintf('  %-10s %s\n', subs{si}, rl_used{si})]; end, end
R=[R sprintf('<<< COPY TO HERE <<<\n')];
fprintf('%s',R);
fid=fopen(fullfile(this_dir,'controller_comparison_report.txt'),'w');
if fid>0, fprintf(fid,'%s',R); fclose(fid); fprintf('Report saved to controller_comparison_report.txt\n'); end

%% ============================ LOCAL FUNCTIONS ============================
function wc=wholecycle(fpath,muscles)
    d=load(fpath,'emg_cycles');
    wc=nan(1,4);
    for k=1:4
        X=cell2mat(d.emg_cycles.(muscles{k})');   % 1001 x n_cycles (raw envelope)
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
function dz=effect_dz(x)
    x=x(~isnan(x)); if numel(x)<2||std(x)==0, dz=NaN; else, dz=mean(x)/std(x); end
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
function s=sig_star(p)
    s=stars(p); if isempty(s), s='n.s.'; end
end
function save_png(h,file,dpi)
    try, exportgraphics(h,file,'Resolution',dpi);
    catch
        set(h,'Units','centimeters'); pp=get(h,'Position');
        set(h,'PaperUnits','centimeters','PaperPositionMode','manual','PaperSize',[pp(3) pp(4)],'PaperPosition',[0 0 pp(3) pp(4)]);
        print(h,file,'-dpng',sprintf('-r%d',dpi));
    end
end
