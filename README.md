# tex-generator
similar to fish-generator but for tex

```bash
# Print length of argument 1
len = argv_len(1);
print(len);

# Loop over each character in argument 1 and output it
i = 0;
while (i < len) {
    ch = argv(1, i);
    putc(ch);
    i = i + 1;
}

println("hello")
```