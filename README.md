# tex-generator
similar to fish-generator but for tex

#### [Inspiration](https://scpchicken.github.io/fish-generator/)
#### Site Link: https://scpchicken.github.io/tex-generator/

### texc docs

```bash
# there is no && or || operators
# newline is chr(13) not chr(10)

# supported operators
# + - * / %
# += -= *= /= %=
# == != < > >= <=

i = 3
j = i
j += 5
println(j)

egg = argc
println(egg)

# Print length of argument 1
len = arglen(1)
print(len)

# Loop over each character in argument 1 and output it
i = 0
while (i < len) {
    ch = argv(1, i)
    putc(ch)
    i = i + 1
}

println("hello")
```