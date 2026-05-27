import { gql } from 'graphql-tag';

const typeDefs = gql`

type Usuario {
  id: ID!
  nombre: String!
  correoElectronico: String!
  contrasena: String!
  firebaseUID: String
  sueldo: Float
  porcentajeRSH: Float
  profesion: String
  fechaNacimiento: Int
  ciudad: String
  region: String
  createdAt: String!
  updatedAt: String!
}

input UsuarioInput {
  nombre: String!
  correoElectronico: String!
  contrasena: String!
  sueldo: Float
  porcentajeRSH: Float
  profesion: String
  fechaNacimiento: Int
  ciudad: String
  region: String
}

input UpdateUsuarioInput {
  nombre: String
  correoElectronico: String
  contrasena: String
  sueldo: Float
  porcentajeRSH: Float
  profesion: String
  fechaNacimiento: Int
  ciudad: String
  region: String
}

type Chat {
  id: ID!
  nombre: String!
  createdAt: String!
  updatedAt: String!
}

input ChatInput {
  nombre: String!
}

type Mensaje {
  id: ID!
  chatID: ID!
  usuarioID: ID
  texto: String
  usuario: Usuario
  archivoAdjuntoURL: String
  createdAt: String!
  updatedAt: String!
}

input MensajeInput {
  chatID: ID!
  usuarioID: ID
  texto: String
  archivoAdjuntoURL: String
}

input ProcessMensajeConIAInput {
  chatID: ID!
  texto: String!
}

type Message {
  message: String!
}

type FileUploadResponse {
  success: Boolean!
  message: String!
  fileUrl: String
}

type MensajeProcesadoConIAResponse {
  mensajeUsuario: Mensaje!
  mensajeIA: Mensaje!
}

type UsuarioLoginResponse {
  success: Boolean!
  message: String!
  usuario: Usuario
}

type UsuarioAuthResponse {
  success: Boolean!
  message: String!
  usuario: Usuario
  firebaseUID: String
  idToken: String
}

input LoginUsuarioInput {
  nombreUsuario: String!
  codigoUsuario: Int!
  contrasena: String!
}

input LoginEmailPasswordInput {
  correoElectronico: String!
  idToken: String!
}

input SignUpEmailPasswordInput {
  nombre: String!
  correoElectronico: String!
  contrasena: String!
}

input LogoutInput {
  idToken: String!
}

input UploadFileInput {
  file: String!
  fileName: String!
  chatID: ID!
}

type Query {
  getUsuarios: [Usuario]
  getUsuarioByID(id: ID!): Usuario
  
  getChats: [Chat]
  getChatByID(id: ID!): Chat
  getChatsByUsuarioID(usuarioID: ID!): [Chat]

  getMensajes(usuarioID: ID!): [Mensaje]
  getMensajeByID(id: ID!, usuarioID: ID!): Mensaje
  getMensajesByChatID(chatID: ID!): [Mensaje]
}

type Mutation {
  addUsuario(input: UsuarioInput!): Usuario
  updUsuario(id: ID!, input: UpdateUsuarioInput!): Usuario
  delUsuario(id: ID!): Message

  addChat(input: ChatInput!): Chat
  updChat(id: ID!, input: ChatInput!): Chat
  delChat(id: ID!): Message

  addMensaje(input: MensajeInput!): Mensaje
  updMensaje(id: ID!, input: MensajeInput!): Mensaje
  delMensaje(id: ID!, usuarioID: ID!): Message
  procesarMensajeConIA(input: ProcessMensajeConIAInput!): MensajeProcesadoConIAResponse

  signUpEmailPassword(input: SignUpEmailPasswordInput!): UsuarioAuthResponse
  loginEmailPassword(input: LoginEmailPasswordInput!): UsuarioAuthResponse
  logout(input: LogoutInput!): UsuarioAuthResponse
  uploadFile(input: UploadFileInput!): FileUploadResponse

  loginUsuario(input: LoginUsuarioInput!): UsuarioLoginResponse
}
`;

export default typeDefs;