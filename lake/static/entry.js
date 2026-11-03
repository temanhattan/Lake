// Choose the welcome route before importing the search application. In demo
// mode, no library/search response is requested until the user starts Lake.
const welcomeOnLaunch = localStorage.getItem('lake-welcome-on-launch') !== '0';
const alreadyStarted = sessionStorage.getItem('lake-welcome-started') === '1';
const entryParams = new URLSearchParams(location.search);
const showWelcome = location.pathname === '/welcome' ||
  (location.pathname === '/' && welcomeOnLaunch && !alreadyStarted);

if (showWelcome) {
  const { startWelcome } = await import('./welcome.js');
  await startWelcome();
} else {
  if (location.pathname !== '/design-system') await import('./app.js');
  await import('./enhancements.js');
  const chatId = entryParams.get('chat');
  if (chatId) window.lakeOpenChat?.(chatId);
  if (entryParams.get('import') === '1') document.querySelector('#import-open')?.click();
}
