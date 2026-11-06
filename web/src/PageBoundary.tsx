import { Component, type ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import { Brand } from './Brand';

export default class PageBoundary extends Component<{children:ReactNode},{error:Error|null}> {
  state:{error:Error|null}={error:null};
  static getDerivedStateFromError(error:Error) { return {error}; }
  render() {
    if (!this.state.error) return this.props.children;
    const updated=/dynamically imported module|Loading chunk|Importing a module script failed/i.test(this.state.error.message);
    return <main className="page-recovery" role="alert"><Brand/><h1>{updated?'Uma nova versão está disponível.':'Não foi possível abrir esta página.'}</h1><p>{updated?'Atualize o sistema para continuar com a versão mais recente.':'Recarregue o sistema para tentar novamente.'}</p><button type="button" onClick={()=>window.location.reload()}><RefreshCw size={18}/> Recarregar sistema</button></main>;
  }
}
