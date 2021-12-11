data = csvread('White_thermistor.csv')
X = data(:, 2)
Y = [ones(size(X)), log(X), log(X).^3]
X = data(:, 3)
Z = pinv(Y)
A = Z*X
csvwrite('output.txt', A)