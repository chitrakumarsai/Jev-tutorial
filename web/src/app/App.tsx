import { ThemeToggle } from '../components/theme-toggle/ThemeToggle';
import './app.css';

export function App() {
  return (
    <>
      <header className="masthead">
        <div className="masthead__title">
          <p className="eyebrow">Typed decisions vs. a plain LLM</p>
          <h1>Jev Audit Lens</h1>
        </div>
        <ThemeToggle />
      </header>
      <main className="workspace" />
    </>
  );
}
