import pandas as pd
df = pd.read_stata("data/raw/ed2022-stata.dta", convert_categoricals=False)
print(df.shape); print(list(df.columns))