
# name   age   city
# 0       Alice   25   Paris
# 1         Bob   31   London
# 2     Charlie   28   Berlin

import pandas as pd

# ***************************************** Series *****************************************

s = pd.Series(
    ["Alice", "Bob", "Charlie"],
    index=["a", "b", "c"]
)

print(type(s))
# pandas.core.series.Series

print(s.index)
# Index(['a', 'b', 'c'], dtype='object')

print(s.values)
# ['Alice' 'Bob' 'Charlie']

print(s['a'])
# Alice

print(s.iloc[1])
# Bob

# ***************************************** DataFrame *****************************************
print('\n')

df = pd.DataFrame({
    "name": ["Alice", "Bob", "Charlie"],
    "age": [25, 31, 28],
    "city": ["Paris", "London", "Berlin"]
})

print(type(df))    # -->> DataFrame típus
# pandas.core.frame.DataFrame

print(type(df["name"]))     # -->> Series típus
# pandas.core.series.Series

print(df["name"])       # -->> Series tartalom
# 0      Alice
# 1        Bob
# 2    Charlie
# Name: name, dtype: object

print(df.index)
# RangeIndex(start=0, stop=3, step=1)   -->> sor indexek

print(df.columns)
# Index(['name', 'age', 'city'], dtype='object')    -->> oszlop nevek

print(df.values)
# [['Alice' 25 'Paris']
#  ['Bob' 31 'London']
#  ['Charlie' 28 'Berlin']]


print(df.iloc[1])     # -->> 1. sor tartalma
# name       Bob
# age         31
# city    London
# Name: 1, dtype: object


print(df.iloc[1,1])     # -->> 1. sor és 1. oszlop tartalma
# age    31


print('Script vége')