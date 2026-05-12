export function plural(n, forms) {
  const num = Math.abs(parseInt(n)) || 0;
  const n10 = num % 10;
  const n100 = num % 100;
  
  if (n100 >= 11 && n100 <= 14) return forms[2];
  if (n10 === 1) return forms[0];
  if (n10 >= 2 && n10 <= 4) return forms[1];
  return forms[2];
}

export function getUserColor(id) {
  const colors = [
    '#3498db', '#9b59b6', '#f1c40f', '#e67e22', 
    '#e74c3c', '#1abc9c', '#34495e', '#2ecc71'
  ];
  if (id === 0) return 'var(--bg-input)';
  return colors[(id - 1) % colors.length];
}