import re

h = open(r"C:\data\pharmnet_home.html", encoding="utf-8").read()
i = h.find("function headers(")
if i < 0:
    i = h.find("headers(")
print(h[max(0, i - 800):i + 900])
print("\n\n=== produits usage ===")
j = h.find("REST+'/produits'")
print(h[max(0, j - 1500):j + 1500])
