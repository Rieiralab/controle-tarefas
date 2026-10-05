-- Estrutura conforme o DER do documento (seção 5).
-- Desvio intencional: usuario.senha é VARCHAR(255) (e não CHAR(12)) para guardar o hash da senha.
-- usuario.nome é UNIQUE porque é usado como login.

CREATE TABLE IF NOT EXISTS usuario (
    codigo  INT AUTO_INCREMENT,
    nome    VARCHAR(50)  NOT NULL,
    direito CHAR(1)      NOT NULL,
    senha   VARCHAR(255) NOT NULL,
    CONSTRAINT pk_usuario PRIMARY KEY (codigo),
    CONSTRAINT uq_usuario_nome UNIQUE (nome),
    CONSTRAINT ck_usuario_direito CHECK (direito IN ('O', 'S'))
);

CREATE TABLE IF NOT EXISTS tarefa (
    codigo INT AUTO_INCREMENT,
    nome   VARCHAR(30) NOT NULL,
    tipo   CHAR(1)     NOT NULL,
    CONSTRAINT pk_tarefa PRIMARY KEY (codigo),
    CONSTRAINT ck_tarefa_tipo CHECK (tipo IN ('D', 'S', 'Q', 'M'))
);

CREATE TABLE IF NOT EXISTS usuario_tarefa (
    cod_usuario INT NOT NULL,
    cod_tarefa  INT NOT NULL,
    CONSTRAINT pk_usuario_tarefa PRIMARY KEY (cod_usuario, cod_tarefa),
    CONSTRAINT fk_usuario FOREIGN KEY (cod_usuario) REFERENCES usuario (codigo) ON DELETE CASCADE,
    CONSTRAINT fk_tarefa  FOREIGN KEY (cod_tarefa)  REFERENCES tarefa (codigo)  ON DELETE CASCADE
);
