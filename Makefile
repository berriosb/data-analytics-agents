PROJECT_DIR := $(shell pwd)
INSTALLER   := node ./bin/install.js
SH_INSTALL  := ./scripts/install.sh
TARGET      := $(HOME)

.PHONY: help \
        install-opencode install-claude install-codex install-agy install-all install-auto \
        uninstall-opencode uninstall-claude uninstall-codex uninstall-agy uninstall-all \
        install-skills uninstall-skills install-sh-agy uninstall-sh-agy cleanup-legacy \
        list skills docs test-csv test-sql test-stats test-ts test-ml test-excel \
        test-export-pdf test-export-ppt test-export-html

help:
	@echo "data-analytics-agents — toolkit multi-CLI de personas"
	@echo ""
	@echo "Inicio rápido (instalación project-local para cualquier CLI)"
	@echo "  make install-opencode    Arregla el descubrimiento de OpenCode (registra 4 personas)"
	@echo "  make install-claude      Project-local: agentes + skills para Claude Code"
	@echo "  make install-codex       Project-local: skills para Codex"
	@echo "  make install-agy         Stagea el plugin de Antigravity (user-level, --global)"
	@echo "  make install-all         Los 4 CLIs a la vez"
	@echo "  make install-auto        Solo para los CLIs que estén en el PATH (--auto)"
	@echo ""
	@echo "Limpieza"
	@echo "  make uninstall-opencode  Elimina los symlinks de OpenCode"
	@echo "  make uninstall-claude    Elimina los symlinks de Claude Code"
	@echo "  make uninstall-codex     Elimina los symlinks de Codex"
	@echo "  make uninstall-agy       Elimina el plugin de Agy"
	@echo "  make uninstall-all       Elimina todo"
	@echo ""
	@echo "User-level (legacy, vía scripts/install.sh)"
	@echo "  make install-skills      Symlinkea skills a ~/.agents/skills/"
	@echo "  make uninstall-skills    Elimina esos symlinks"
	@echo "  make cleanup-legacy      Elimina symlinks VIEJOS por CLI de revisiones anteriores"
	@echo ""
	@echo "Descubrimiento / smoke tests"
	@echo "  make list         Muestra qué está instalado y dónde"
	@echo "  make skills       Muestra las 13 skills a nivel usuario"
	@echo "  make docs         Abre los archivos markdown clave"
	@echo "  make test-csv     Smoke test de csv-profiler sobre examples/ventas_sample.csv"
	@echo "  make test-sql     Conecta a examples/notes_example.sqlite"
	@echo "  make test-stats   Smoke test de statistical-testing sobre datos sintéticos"
	@echo "  make test-ts      Smoke test de time-series-patterns sobre una serie sintética"
	@echo "  make test-ml      Smoke test de feature-engineering + ml-modeling + model-evaluation"
	@echo "  make test-excel   Smoke test de excel-profiler sobre examples/excel_sample/"
	@echo "  make test-export-pdf   Smoke test de report-export formato PDF"
	@echo "  make test-export-ppt   Smoke test de report-export formato PPTX"
	@echo "  make test-export-html  Smoke test de report-export formato HTML standalone"

# ---- instalaciones project-local (la ruta principal) ------------------------

install-opencode:
	$(INSTALLER) install --opencode

install-claude:
	$(INSTALLER) install --claude

install-codex:
	$(INSTALLER) install --codex

install-agy:
	$(INSTALLER) install --agy --global

install-all: install-opencode install-claude install-codex install-agy

install-auto:
	$(INSTALLER) install --auto

# ---- desinstalaciones ------------------------------------------------------

uninstall-opencode:
	$(INSTALLER) uninstall --opencode

uninstall-claude:
	$(INSTALLER) uninstall --claude

uninstall-codex:
	$(INSTALLER) uninstall --codex

uninstall-agy:
	$(INSTALLER) uninstall --agy --global

uninstall-all: uninstall-opencode uninstall-claude uninstall-codex uninstall-agy

# ---- instalaciones user-level legacy (para usuarios sin Node 18+) ------------

install-skills:
	$(SH_INSTALL) install-skills --target $(TARGET)

uninstall-skills:
	$(SH_INSTALL) uninstall-skills --target $(TARGET)

install-sh-agy:
	$(SH_INSTALL) install-agy --target $(TARGET)

uninstall-sh-agy:
	$(SH_INSTALL) uninstall-agy --target $(TARGET)

cleanup-legacy:
	$(SH_INSTALL) cleanup-legacy --target $(TARGET)

# ---- descubrimiento --------------------------------------------------------

list:
	@echo "--- raíz del proyecto (AGENTS.md auto-descubierto por los 4 CLIs) ---"
	@ls -1 $(PROJECT_DIR)/AGENTS.md
	@echo ""
	@echo "--- agents/ (fuente de verdad de las personas) ---"
	@ls -1 $(PROJECT_DIR)/agents/
	@echo ""
	@echo "--- skills/ (fuente de verdad de las skills) ---"
	@ls -1 $(PROJECT_DIR)/skills/
	@echo ""
	@echo "--- instalaciones project-local (./.opencode, ./.claude, ./.agents) ---"
	@ls -la $(PROJECT_DIR)/.opencode 2>/dev/null || echo "  (no hay .opencode/ — corré 'make install-opencode')"
	@ls -la $(PROJECT_DIR)/.claude 2>/dev/null || echo "  (no hay .claude/ — corré 'make install-claude')"
	@ls -la $(PROJECT_DIR)/.agents 2>/dev/null || echo "  (no hay .agents/ — corré 'make install-codex')"
	@echo ""
	@echo "--- skills user-level (~/.agents/skills/, compartidas por todos los CLIs) ---"
	@ls -1 $(HOME)/.agents/skills/ 2>/dev/null | grep -E "(csv-profiler|pandas-cleaning|sql-query-helper|schema-mapper|query-validation|viz-patterns|insight-synthesis|statistical-testing|time-series-patterns|feature-engineering|ml-modeling|model-evaluation|using-data-analytics-agents)" || echo "  (ninguna — corré 'make install-skills')"
	@echo ""
	@echo "--- plugin de Antigravity (user-level, opcional) ---"
	@ls -1 $(HOME)/.gemini/antigravity-cli/plugins/data-analytics-agents/ 2>/dev/null || echo "  (no instalado — corré 'make install-agy')"
	@echo ""
	@echo "--- agentes registrados en OpenCode ---"
	@opencode agent list 2>/dev/null | grep -E "^[a-z][a-z-]+ \(" | sort -u || echo "  (opencode no está en el PATH)"

skills:
	@ls -1 $(HOME)/.agents/skills/ 2>/dev/null | grep -E "(csv-profiler|pandas-cleaning|sql-query-helper|schema-mapper|query-validation|viz-patterns|insight-synthesis|statistical-testing|time-series-patterns|feature-engineering|ml-modeling|model-evaluation|using-data-analytics-agents)"

docs:
	@echo "Abrí estos:"
	@echo "  $(PROJECT_DIR)/AGENTS.md              — punto de entrada (lo leen todos los CLIs)"
	@echo "  $(PROJECT_DIR)/agents/<name>.md       — prompts detallados de las personas"
	@echo "  $(PROJECT_DIR)/skills/<name>/SKILL.md — cuerpos detallados de las skills"
	@echo "  $(PROJECT_DIR)/bin/install.js         — instalador multi-CLI"

test-csv:
	@echo "Corre los snippets de csv-profiler localmente sobre examples/ventas_sample.csv"
	@python3 -c "import pandas as pd, numpy as np; df=pd.read_csv('examples/ventas_sample.csv'); df=df.replace(['','nan','NaN','null','NULL','None','?'], np.nan); df=df.replace([np.inf,-np.inf], np.nan); print('forma:', df.shape); print('nulos por columna:'); print(df.isna().sum()); print('duplicados:', int(df.duplicated().sum()))"

test-sql:
	@echo "Conecta a examples/notes_example.sqlite"
	@python3 -c "import sqlite3; c=sqlite3.connect('examples/notes_example.sqlite'); print('clientes/productos/pedidos:', c.execute('SELECT (SELECT count(*) FROM customers),(SELECT count(*) FROM products),(SELECT count(*) FROM orders)').fetchone())"

test-stats:
	@echo "Smoke test de statistical-testing con datos sintéticos (Welch, ANOVA, chi², Shapiro)"
	@python3 -c "import numpy as np; from scipy import stats; np.random.seed(42); a=np.random.normal(10,2,80); b=np.random.normal(11,2.5,75); welch=stats.ttest_ind(a,b,equal_var=False); anova=stats.f_oneway(a,b,np.random.normal(12,2,90)); shap=stats.shapiro(a); chi2=stats.chi2_contingency(np.array([[30,20,10],[25,30,35]])); print('Welch t-test p=%.4f n=%d' % (welch.pvalue, len(a)+len(b))); print('ANOVA p=%.4e n=%d' % (anova.pvalue, len(a)+len(b)+90)); print('Shapiro p=%.4f n=%d' % (shap.pvalue, len(a))); print('Chi2 p=%.4f n=%d' % (chi2[1], 150))"

test-ts:
	@echo "Smoke test de time-series-patterns (lite, sin statsmodels) sobre serie sintética con periodicidad semanal"
	@python3 -c "import numpy as np, pandas as pd; np.random.seed(42); idx=pd.date_range('2023-01-01', periods=365, freq='D'); s=pd.Series(np.linspace(100,200,365)+20*np.sin(2*np.pi*np.arange(365)/7)+np.random.normal(0,5,365), index=idx); m=s.resample('MS').mean(); rs=s.rolling(7).mean(); per=[float((s.values[:-k]-s.values.mean()).dot(s.values[k:]-s.values.mean())/((s.values-s.values.mean())**2).sum()) for k in range(1,31)]; fc=s.iloc[-1]; print('resample MS n_periods=%d, mean(recent 30d)=%.2f' % (len(m), s.iloc[-30:].mean())); print('rolling 7d non-null=%d, last=%.2f' % (rs.notna().sum(), rs.iloc[-1])); print('best lag=%d, autocorr=%.4f (esperado 7)' % (int(np.argmax(per))+1, max(per))); print('naive forecast (last) = %.2f' % fc)"

test-ml:
	@echo "Smoke test de feature-engineering + ml-modeling + model-evaluation (clasif. binaria + regresión)"
	@python3 -c "import numpy as np, pandas as pd; from sklearn.linear_model import LogisticRegression, LinearRegression; from sklearn.model_selection import train_test_split, cross_val_score; np.random.seed(42); n=1000; X=pd.DataFrame({'a':np.random.normal(0,1,n),'b':np.random.uniform(-1,1,n),'c':np.random.choice(['x','y'],n)}); y=(X['a']+0.5*(X['c']=='x')+np.random.normal(0,0.3,n)>0).astype(int); X_enc=pd.get_dummies(X, columns=['c'], drop_first=True).astype(float); Xtr,Xte,ytr,yte=train_test_split(X_enc.values,y.values,test_size=0.2,random_state=42,stratify=y.values); lr=LogisticRegression(max_iter=1000,random_state=42); lr.fit(Xtr,ytr); cv=cross_val_score(lr,Xtr,ytr,cv=3,scoring='roc_auc'); print('clasif: CV ROC-AUC=%.3f +/- %.3f, test acc=%.3f' % (cv.mean(), cv.std(), (lr.predict(Xte)==yte).mean())); X2=pd.DataFrame({'a':np.random.uniform(0,1,n),'b':np.random.uniform(0,1,n)}); y2=3*X2['a']-2*X2['b']+np.random.normal(0,0.1,n); Xtr2,Xte2,ytr2,yte2=train_test_split(X2.values,y2.values,test_size=0.2,random_state=42); rg=LinearRegression(); rg.fit(Xtr2,ytr2); cv2=cross_val_score(rg,Xtr2,ytr2,cv=3,scoring='r2'); print('regresion: CV R2=%.3f +/- %.3f, test R2=%.3f' % (cv2.mean(), cv2.std(), rg.score(Xte2,yte2)))"

test-excel:
	@echo "Smoke test de excel-profiler sobre examples/excel_sample/ventas_q2_2026_dirty.xlsx"
	@python3 examples/excel_sample/test_excel_profiler.py

test-export-pdf:
	@echo "Smoke test de report-export (PDF) — genera sample si falta, exporta y valida"
	@if [ ! -f examples/report_export_sample/charts/figura_1_revenue_lineal.png ]; then python3 examples/report_export_sample/generate_sample.py; fi
	@python3 examples/report_export_sample/export_demo.py 2>&1 | tail -20

test-export-ppt:
	@echo "Smoke test de report-export (PPTX)"
	@if [ ! -f examples/report_export_sample/charts/figura_1_revenue_lineal.png ]; then python3 examples/report_export_sample/generate_sample.py; fi
	@python3 -c "import sys; sys.path.insert(0, '.'); from skills_loader import load_skill_packages; load_skill_packages('skills'); from report_export.recetas import parse_insights_markdown, build_ppt, verify_ppt; from pathlib import Path; insights=parse_insights_markdown('examples/report_export_sample/insights.md'); charts=sorted(Path('examples/report_export_sample/charts').glob('*.png')); out=build_ppt(insights, charts, None, 'examples/report_export_sample/out/reporte.pptx'); print('verify_ppt:', 'OK' if verify_ppt(out) else 'FAIL', out.stat().st_size, 'bytes')"

test-export-html:
	@echo "Smoke test de report-export (HTML standalone)"
	@if [ ! -f examples/report_export_sample/charts/figura_1_revenue_lineal.png ]; then python3 examples/report_export_sample/generate_sample.py; fi
	@python3 -c "import sys; sys.path.insert(0, '.'); from skills_loader import load_skill_packages; load_skill_packages('skills'); from report_export.recetas import parse_insights_markdown, build_html, verify_html; from pathlib import Path; insights=parse_insights_markdown('examples/report_export_sample/insights.md'); charts=sorted(Path('examples/report_export_sample/charts').glob('*.png')); templates=Path('skills/report-export/templates'); out=build_html(insights, charts, templates, 'examples/report_export_sample/out/reporte.html'); print('verify_html:', 'OK' if verify_html(out) else 'FAIL', out.stat().st_size, 'bytes')"