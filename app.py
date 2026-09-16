"""Run with: python -m streamlit run app.py"""
import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
st.set_page_config(page_title='Semiconductor Test Analytics', page_icon='🔬', layout='wide')
st.markdown('<style>.block-container{padding-top:2.5rem;max-width:1400px} '
            '[data-testid="stMetric"]{background:#f0f6f8;border:1px solid #d8e6eb;'
            'border-radius:10px;padding:16px;color:#123}</style>', unsafe_allow_html=True)
st.caption('ENGINEERING PORTFOLIO  /  PYTHON + SQL  /  SYNTHETIC DATA')
st.title('Semiconductor Test Analytics')
st.write('Trace a yield change from lot-level results to individual electrical measurements.')
if not (OUT / 'summary.json').exists():
    st.error('Run python pipeline.py from the project folder first.')
    st.stop()
summary = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
data = pd.read_csv(OUT/'valid_tests.csv')
rejected = pd.read_csv(OUT/'quarantined_tests.csv')

st.sidebar.header('Investigate measurements')
selected = st.sidebar.multiselect('Lots', sorted(data.lot_id.unique()), default=sorted(data.lot_id.unique()))
temp = st.sidebar.selectbox('Temperature (°C)', ['All', -40, 25, 85])
voltage = st.sidebar.selectbox('Supply voltage (V)', ['All', 3.0, 3.3, 3.6])
st.sidebar.caption('One assigned test condition per device. Filters compare different devices, not repeated sweeps.')
view = data[data.lot_id.isin(selected)].copy()
if temp != 'All':
    view = view[view.temperature_c == temp]
if voltage != 'All':
    view = view[view.voltage_v == voltage]
if view.empty:
    st.info('Select at least one lot with matching measurements.')
    st.stop()
view['passed'] = (view.test_result == 'PASS').astype(int)
cols = st.columns(4)
for col, label, value in zip(cols, ['Valid devices in view', 'Observed yield', 'Failed devices', 'Quarantined rows · all data'],
    [f'{len(view):,}', f'{100*view.passed.mean():.2f}%', f'{(view.test_result == "FAIL").sum():,}', str(len(rejected))]):
    col.metric(label, value)
st.caption('Yield = passing valid devices / all valid devices. Quarantined records are disclosed separately.')
tabs = st.tabs(['Yield investigation', 'Measurement detail', 'Data quality & method'])
with tabs[0]:
    lots = view.groupby('lot_id').agg(devices=('passed', 'size'), passed=('passed', 'sum'),
                                    mean_leakage_ua=('leakage_ua', 'mean')).reset_index()
    lots['yield_percent'] = 100 * lots.passed / lots.devices
    worst = lots.loc[lots.yield_percent.idxmin()]
    st.info(f'Lowest yield in this view: {worst.lot_id} · {worst.yield_percent:.2f}% '
            f'across {int(worst.devices):,} valid devices. Compare leakage at matching temperature and voltage.')
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader('Yield by lot')
        chart = alt.Chart(lots).mark_bar(color='#087e8b', cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X('lot_id:N', title='Lot'), y=alt.Y('yield_percent:Q', title='Yield (%)', scale=alt.Scale(domain=[0,100])),
            tooltip=['lot_id', 'devices', alt.Tooltip('yield_percent:Q', format='.2f')]).properties(height=300)
        st.altair_chart(chart, width='stretch')
    with right:
        st.subheader('Specification violations')
        modes = view.loc[view.test_result == 'FAIL', 'failure_modes'].str.split('|').explode().value_counts()
        if len(modes):
            frame = modes.rename_axis('failure_mode').reset_index(name='devices')
            st.altair_chart(alt.Chart(frame).mark_bar(color='#d47b43').encode(
                y=alt.Y('failure_mode:N', sort='-x', title=None), x=alt.X('devices:Q', title='Devices'),
                tooltip=['failure_mode','devices']).properties(height=300), width='stretch')
        else:
            st.success('No specification violations in the selected data.')
        st.caption('A device can violate several limits; counts can exceed the number of failed devices.')
    st.subheader('Wafer investigation')
    wafers = view.groupby(['lot_id','wafer_id']).agg(devices=('passed','size'), yield_fraction=('passed','mean')).reset_index()
    wafers['yield_percent'] = (100*wafers.pop('yield_fraction')).round(2)
    st.dataframe(wafers.sort_values('yield_percent'), hide_index=True, width='stretch')
with tabs[1]:
    st.subheader('Leakage shift across lots')
    # All rows contribute to each summary; no chart sampling or row-limit override needed.
    stats = view.groupby('lot_id').leakage_ua.agg(median='median',
        p10=lambda x: x.quantile(.1), p90=lambda x: x.quantile(.9)).reset_index()
    base = alt.Chart(stats).encode(x=alt.X('lot_id:N', title='Lot'))
    band = base.mark_area(opacity=.18, color='#087e8b').encode(y=alt.Y('p10:Q', title='Leakage (µA)'), y2='p90:Q')
    line = base.mark_line(point=True, color='#087e8b').encode(y='median:Q', tooltip=['lot_id','median','p10','p90'])
    limit = alt.Chart(pd.DataFrame({'limit':[10]})).mark_rule(color='#ca493e', strokeDash=[6,4]).encode(y='limit:Q')
    st.altair_chart((band+line+limit).properties(height=330), width='stretch')
    st.caption('Line: median. Shaded band: 10th–90th percentiles. Dashed red line: illustrative 10 µA upper limit. '
               'Use matching temperature and supply settings before comparing lots.')
    st.subheader('Device records')
    outcome = st.selectbox('Show outcomes', ['All','FAIL','PASS'])
    rows = view if outcome == 'All' else view[view.test_result == outcome]
    st.dataframe(rows.drop(columns='passed').head(500), hide_index=True, width='stretch')
    st.caption('Table shows up to 500 rows. Download includes all records matching the filters.')
    st.download_button('Download selected measurements', rows.drop(columns='passed').to_csv(index=False),
                       'selected_measurements.csv', 'text/csv')
with tabs[2]:
    st.subheader('Global data-quality accounting')
    st.write(f"{summary['raw_rows']:,} raw rows = {summary['valid_devices']:,} valid device records + "
             f"{summary['quarantined_rows']} quarantined rows. {summary['devices_without_valid_result']} of "
             f"{summary['unique_devices_raw']:,} unique devices have no valid result.")
    st.warning('A valid high-leakage measurement is a device failure, not a corrupt record. '
               'Excluded devices can bias observed yield; the dashboard does not estimate their outcomes.')
    st.dataframe(rejected.rejection_reason.value_counts().rename_axis('Reason').reset_index(name='Rows'), hide_index=True)
    st.download_button('Download quarantined records', rejected.to_csv(index=False), 'quarantined_tests.csv', 'text/csv')
    st.subheader('Illustrative test limits')
    st.table(pd.DataFrame({'Parameter':['Leakage','Current','Gain'], 'Passing condition':['≤ 10 µA','≤ 60 mA','≥ 18 dB']}))
    st.markdown('''- **Synthetic only:** no Skyworks data, specifications, or proprietary processes.
- **Ground truth:** the generator gradually increases leakage in lots L09–L12; additional random defects are injected.
- **One row per device:** one assigned temperature and supply; no retests or repeated condition sweeps.
- **Validation:** first occurrence of a device ID is retained if valid; later occurrences are quarantined. This policy is for this single-run dataset.
- **Interpretation:** the drift is an investigative signal; correlated measurements do not establish physical root cause.
- **Scope:** Python, SQLite/SQL, validation, dashboard, and an HTML report. ML, PySpark, real instrument control, and cloud deployment are future work.
- **DC power:** voltage in volts × current in milliamps gives milliwatts; this is not RF output power or efficiency.
''')
    st.download_button('Download offline engineering report', (OUT/'report.html').read_bytes(), 'report.html', 'text/html')
    st.code((ROOT/'sql'/'analytics.sql').read_text(encoding='utf-8'), language='sql')
