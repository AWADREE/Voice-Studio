(file) => {
  if (!file?.url) return;
  const link = document.createElement('a');
  link.href = file.url;
  link.download = file.orig_name || file.path?.split(/[\\/]/).pop() || 'voice.pt';
  document.body.appendChild(link);
  link.click();
  link.remove();
}
